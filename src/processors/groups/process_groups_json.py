import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from models.matrix_config import DEFAULT_MATRIX, MatrixConfig
from models.pad_filter_config import DEFAULT_PAD_FILTER, PadFilterConfig
from utils.audio_utils import trim_and_normalize_wav
from utils.logger import Logger

logger = Logger.get_logger("GroupsProcessor")


def pick_multisample_path(paths):
    # Prioritize _C4, _C3
    for p in paths:
        base = os.path.splitext(p)[0].upper()  # case-insensitive
        if base.endswith('_C4'):
            return p
        if base.endswith('_C3'):
            return p

    # Then match _C followed by any single digit
    for p in paths:
        base = os.path.splitext(p)[0].upper()
        if re.search(r'_C\d$', base):
            return p

    # Fallback to the first path
    return paths[0]

class GroupsProcessor:
    def __init__(
        self,
        json_path,
        output_folder,
        trim_silence=False,
        matrix=None,
        filter_pads=True,
        pad_filter=None,
        fill_blanks=None,
        normalize=False,
        sample_rate=None,
        bit_depth=None,
        enable_matrix=True,
        include_preview=False
    ):
        self.json_path = json_path
        self.output_folder = output_folder
        self.trim_silence = trim_silence
        self.matrix = matrix if matrix is not None else DEFAULT_MATRIX
        self.filter_pads = filter_pads
        self.pad_filter = pad_filter if pad_filter is not None else DEFAULT_PAD_FILTER
        self.fill_blanks = fill_blanks
        self.normalize = normalize
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.enable_matrix = enable_matrix
        self.include_preview = include_preview

    def run(self, worker_instance=None):  # Accept worker_instance
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                groups = json.load(f)

            def pad_contains(sample, keywords):
                if not sample:
                    return False
                name = sample.get('name', '')
                name = name.lower()
                return any(kw in name for kw in keywords)

            filtered_groups = []
            if self.filter_pads and self.pad_filter:
                for group in groups:
                    if worker_instance and worker_instance.cancel_requested():  # Check for cancellation
                        logger.info("Groups export cancelled by user.")
                        return 1  # Return non-zero for cancellation
                    samples = group.get('samples', [])
                    match = True
                    for pad_num, keywords in self.pad_filter.pads.items():
                        pad_sample = next((s for s in samples if s.get('pad') == pad_num), None)
                        if not pad_contains(pad_sample, keywords):
                            match = False
                            break
                    if match:
                        filtered_groups.append(group)
                groups = filtered_groups

            for group in groups:
                if worker_instance and worker_instance.cancel_requested():  # Check for cancellation
                    logger.info("Groups export cancelled by user.")
                    return 1  # Return non-zero for cancellation

                group_name = group['group']
                expansion_name = group['expansion']
                base_path = group['path']
                samples = group['samples']

                group_folder = os.path.join(self.output_folder, expansion_name, group_name)
                os.makedirs(group_folder, exist_ok=True)

                pad_to_sample = {}
                for s in samples:
                    pad_to_sample[s['pad']] = s

                for original_pad in range(1, 17):
                    if worker_instance and worker_instance.cancel_requested():  # Check for cancellation
                        logger.info("Groups export cancelled by user.")
                        return 1  # Return non-zero for cancellation

                    sample = pad_to_sample.get(original_pad)
                    # Access the internal dictionary of MatrixConfig
                    target_pad = self.matrix.pads.get(original_pad, original_pad) if self.enable_matrix else original_pad
                    suffix = f"{target_pad:02d}_"

                    if sample:
                        if sample['type'] == 'multisample':
                            source_rel_path = pick_multisample_path(sample['paths'])
                        else:
                            source_rel_path = sample['paths']

                        source_path = os.path.join(base_path, source_rel_path)
                        if not os.path.isfile(source_path):
                            logger.warning(f"Source file not found {source_path}")
                            continue

                        filename = os.path.basename(source_path)
                        target_filename = suffix + filename
                        target_path = os.path.join(group_folder, target_filename)

                        try:
                            trim_and_normalize_wav(source_path, target_path, self.trim_silence, self.normalize, self.sample_rate, self.bit_depth)
                        except Exception as e:
                            logger.error(f"Error processing {source_path}: {e}")
                            shutil.copy2(source_path, target_path)

                        logger.info(f"Copied pad {original_pad:02d} -> target pad {target_pad:02d} file: {target_path}")
                    else:
                        if self.fill_blanks:
                            import random
                            if os.path.isdir(self.fill_blanks):
                                wavs = [f for f in os.listdir(self.fill_blanks) if f.lower().endswith('.wav')]
                                if wavs:
                                    chosen = random.choice(wavs)
                                    source_path = os.path.join(self.fill_blanks, chosen)
                                else:
                                    source_path = None
                            else:
                                source_path = self.fill_blanks
                            if source_path and os.path.isfile(source_path):
                                target_filename = suffix + os.path.basename(source_path)
                                target_path = os.path.join(group_folder, target_filename)
                                try:
                                    trim_and_normalize_wav(source_path, target_path, self.trim_silence, self.normalize, self.sample_rate, self.bit_depth)
                                except Exception as e:
                                    logger.error(f"Error processing {source_path}: {e}")
                                    shutil.copy2(source_path, target_path)
                                logger.info(f"Filled blank pad {original_pad:02d} -> target pad {target_pad:02d} with: {target_path}")
                            else:
                                logger.warning(f"No valid file to fill blank pad {original_pad:02d}")
                if self.include_preview:
                    preview_dir = os.path.join(base_path, "Groups", "groups", ".previews")
                    preview_file = os.path.join(preview_dir, group_name + ".mxgrp.ogg")
                    if os.path.isfile(preview_file):
                        preview_wav = os.path.join(group_folder, "Preview - " + group_name + ".wav")
                        try:
                            trim_and_normalize_wav(preview_file, preview_wav, self.trim_silence, self.normalize, self.sample_rate, self.bit_depth)
                            logger.info(f"Included preview sample: {preview_wav}")
                        except Exception as e:
                            logger.error(f"Error processing preview {preview_file}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error processing groups: {e}")
            return 1


def main(
    json_path: str,
    output_folder: str,
    trim_silence: bool,
    normalize: bool,
    matrix_json: str,
    filter_pads: bool,
    filter_pads_json: str,
    fill_blanks: bool,
    fill_blanks_path: str,
    sample_rate: int,
    bit_depth: int,
    enable_matrix: bool,
    include_preview: bool
):
    # Matrix
    if matrix_json:
        with open(matrix_json, 'r', encoding='utf-8') as f:
            loaded_dict = {int(k): v for k, v in json.load(f).items()}
            matrix = MatrixConfig(loaded_dict)
    else:
        matrix = MatrixConfig()

    # Pad filter
    if filter_pads_json:
        with open(filter_pads_json, 'r', encoding='utf-8') as f:
            loaded_dict = {int(k): v for k, v in json.load(f).items()}
            pad_filter = PadFilterConfig(loaded_dict)
    else:
        pad_filter = PadFilterConfig()

    actual_fill_blanks_path = None
    if fill_blanks and fill_blanks_path:
        actual_fill_blanks_path = fill_blanks_path

    processor = GroupsProcessor(
        json_path=json_path,
        output_folder=output_folder,
        trim_silence=trim_silence,
        matrix=matrix,
        filter_pads=filter_pads,
        pad_filter=pad_filter,
        fill_blanks=actual_fill_blanks_path,
        normalize=normalize,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        enable_matrix=enable_matrix,
        include_preview=include_preview
    )
    sys.exit(processor.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="group processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action='store_true', help="Trim silence from wav files")
    parser.add_argument("--normalize", action='store_true', help="Normalize wav files")
    parser.add_argument("--matrix_json", help="Optional custom reorder matrix JSON file")
    parser.add_argument("--filter_pads", action='store_true', help="Filter groups: pad 1 contains keywords for pad 1, pad 2 for pad 2, pad 3 for pad 3 (case-insensitive)")
    parser.add_argument("--filter_pads_json", help="Optional custom pad filter keywords JSON file")
    parser.add_argument("--fill_blanks", action='store_true', help="Fill blank pads")
    parser.add_argument("--fill_blanks_path", help="Fill blank pads with file or folder of wavs (default: ./assets/.wav)", default="./assets/.wav")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")
    parser.add_argument("--enable_matrix", action='store_true', help="Enable pad matrix reorder")
    parser.add_argument("--include_preview", action='store_true', help="Include preview samples from groups.previews")

    args = parser.parse_args()

    # Parameter Validation
    if not Path(args.json_path).is_file():
        logger.error(f"Error: JSON path '{args.json_path}' does not exist or is not a file.")
        sys.exit(1)

    output_dir = Path(args.output_folder)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error: Could not create output folder '{args.output_folder}': {e}")
        sys.exit(1)

    if args.matrix_json and not Path(args.matrix_json).is_file():
        logger.error(f"Error: Matrix JSON path '{args.matrix_json}' does not exist or is not a file.")
        sys.exit(1)

    if args.filter_pads_json and not Path(args.filter_pads_json).is_file():
        logger.error(f"Error: Pad filter JSON path '{args.filter_pads_json}' does not exist or is not a file.")
        sys.exit(1)

    if args.fill_blanks and args.fill_blanks_path:
        fill_path = Path(args.fill_blanks_path)
        if not fill_path.exists():
            logger.error(f"Error: Fill blanks path '{args.fill_blanks_path}' does not exist.")
            sys.exit(1)
        if not (fill_path.is_file() or fill_path.is_dir()):
            logger.error(f"Error: Fill blanks path '{args.fill_blanks_path}' is not a file or a directory.")
            sys.exit(1)

    if args.sample_rate is not None and args.sample_rate <= 0:
        logger.error(f"Error: Sample rate must be a positive integer, got {args.sample_rate}.")
        sys.exit(1)

    if args.bit_depth is not None and args.bit_depth <= 0:
        logger.error(f"Error: Bit depth must be a positive integer, got {args.bit_depth}.")
        sys.exit(1)

    try:
        main(
            json_path=args.json_path,
            output_folder=args.output_folder,
            trim_silence=args.trim_silence,
            normalize=args.normalize,
            matrix_json=args.matrix_json,
            filter_pads=args.filter_pads,
            filter_pads_json=args.filter_pads_json,
            fill_blanks=args.fill_blanks,
            fill_blanks_path=args.fill_blanks_path,
            sample_rate=args.sample_rate,
            bit_depth=args.bit_depth,
            enable_matrix=args.enable_matrix,
            include_preview=args.include_preview
        )
    except SystemExit as e:
        sys.exit(e.code)
