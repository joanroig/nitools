import json
import os
import shutil
import sys
from difflib import SequenceMatcher
from pathlib import Path

from models.matrix_config import DEFAULT_MATRIX, MatrixConfig
from models.pad_filter_config import DEFAULT_PAD_FILTER, PadFilterConfig
from utils.audio_utils import trim_and_normalize_wav
from utils.logger import Logger

logger = Logger.get_logger("KitsProcessor")


def _find_samples_root(nbkt_path: str) -> str | None:
    """Walk up from the kit file until we find a directory containing a 'Samples' folder."""
    path = os.path.dirname(os.path.abspath(nbkt_path))
    while True:
        if os.path.isdir(os.path.join(path, "Samples")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def _list_all_wavs(samples_root: str) -> list[str]:
    """Return all .wav files under <samples_root>/Samples/."""
    base = os.path.join(samples_root, "Samples")
    if not os.path.isdir(base):
        return []
    result = []
    for root, _, files in os.walk(base):
        for f in files:
            if f.lower().endswith(".wav"):
                result.append(os.path.join(root, f))
    return result


def _find_sample_file(sample_name: str, samples_root: str) -> str | None:
    """Search recursively for a file with the given name under <samples_root>/Samples/."""
    base = os.path.join(samples_root, "Samples")
    if not os.path.isdir(base):
        return None
    name_lower = sample_name.lower()
    for root, _, files in os.walk(base):
        for f in files:
            if f.lower() == name_lower:
                return os.path.join(root, f)
    return None


def _best_match(sample_name: str, candidates: list[str]) -> str | None:
    """Return the candidate .wav whose stem is most similar to sample_name (stem)."""
    stem = os.path.splitext(sample_name)[0].lower()
    best_ratio = 0.0
    best_path = None
    for cand in candidates:
        cand_stem = os.path.splitext(os.path.basename(cand))[0].lower()
        ratio = SequenceMatcher(None, stem, cand_stem).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_path = cand
    return best_path if best_ratio >= 0.4 else None


class KitsProcessor:
    def __init__(
        self,
        json_path: str,
        output_folder: str,
        trim_silence: bool = False,
        normalize: bool = False,
        sample_rate: int | None = None,
        bit_depth: int | None = None,
        matrix=None,
        enable_matrix: bool = True,
        filter_pads: bool = False,
        pad_filter=None,
        include_preview: bool = False,
        skip_existing: bool = False,
        replace_missing: bool = True,
    ):
        self.json_path = json_path
        self.output_folder = output_folder
        self.trim_silence = trim_silence
        self.normalize = normalize
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.matrix = matrix if matrix is not None else DEFAULT_MATRIX
        self.enable_matrix = enable_matrix
        self.filter_pads = filter_pads
        self.pad_filter = pad_filter if pad_filter is not None else DEFAULT_PAD_FILTER
        self.include_preview = include_preview
        self.skip_existing = skip_existing
        self.replace_missing = replace_missing

    def run(self, worker_instance=None):
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                kits = json.load(f)

            # Optional pad filter (same logic as groups)
            if self.filter_pads and self.pad_filter:
                filtered = []
                for kit in kits:
                    samples = kit.get("samples", [])
                    match = True
                    for pad_num, keywords in self.pad_filter.pads.items():
                        pad_sample = next((s for s in samples if s.get("pad") == pad_num), None)
                        name = (pad_sample or {}).get("path", "").lower()
                        if not any(kw in name for kw in keywords):
                            match = False
                            break
                    if match:
                        filtered.append(kit)
                kits = filtered

            for kit in kits:
                if worker_instance and worker_instance.cancel_requested():
                    logger.info("Kits export cancelled by user.")
                    return 1

                kit_name = kit.get("kit", "Unknown")
                nbkt_path = kit.get("path", "")
                samples = kit.get("samples", [])

                samples_root = _find_samples_root(nbkt_path) if nbkt_path else None
                all_wavs: list[str] = _list_all_wavs(samples_root) if samples_root else []

                kit_folder = os.path.join(self.output_folder, _safe_name(kit_name))
                os.makedirs(kit_folder, exist_ok=True)

                # Apply matrix reorder
                ordered = list(range(len(samples)))
                if self.enable_matrix and self.matrix and len(samples) >= 16:
                    flat = [self.matrix.grid[r][c] - 1 for r in range(4) for c in range(4)]
                    ordered = [flat[i] if 0 <= flat[i] < len(samples) else i
                                for i in range(min(16, len(samples)))]
                    ordered += list(range(16, len(samples)))

                for out_idx, src_idx in enumerate(ordered, start=1):
                    if src_idx >= len(samples):
                        continue
                    sample = samples[src_idx]
                    sample_name = sample.get("path", "")
                    if not sample_name:
                        continue

                    src_path = _find_sample_file(sample_name, samples_root) if samples_root else None

                    if src_path is None:
                        if self.replace_missing and all_wavs:
                            src_path = _best_match(sample_name, all_wavs)
                            if src_path:
                                logger.info(f"  [{kit_name}] pad {out_idx}: '{sample_name}' not found, "
                                            f"replaced with '{os.path.basename(src_path)}'")
                            else:
                                logger.warning(f"  [{kit_name}] pad {out_idx}: '{sample_name}' — no match found, skipping.")
                                continue
                        else:
                            logger.warning(f"  [{kit_name}] pad {out_idx}: '{sample_name}' not found, skipping.")
                            continue

                    out_name = f"{out_idx:02d}.wav"
                    out_path = os.path.join(kit_folder, out_name)

                    if self.skip_existing and os.path.exists(out_path):
                        logger.info(f"  [{kit_name}] pad {out_idx}: skipped (already exists).")
                        continue

                    try:
                        if self.trim_silence or self.normalize or self.sample_rate or self.bit_depth:
                            trim_and_normalize_wav(
                                src_path, out_path,
                                trim=self.trim_silence,
                                normalize=self.normalize,
                                sample_rate=self.sample_rate,
                                bit_depth=self.bit_depth,
                            )
                        else:
                            shutil.copy2(src_path, out_path)
                    except Exception as e:
                        logger.error(f"  [{kit_name}] pad {out_idx}: error copying '{sample_name}': {e}")
                        continue

                logger.info(f"Exported kit: {kit_name} → {kit_folder}")

            logger.info(f"All kits exported to {self.output_folder}")
            return 0

        except Exception as e:
            logger.error(f"Error exporting kits: {e}")
            return 1


def _safe_name(name: str) -> str:
    """Replace characters that are not valid in folder names."""
    import re
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()
