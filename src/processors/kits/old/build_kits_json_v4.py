import argparse
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

from utils.file_utils import ensure_unique_path, sanitize
from utils.logger import Logger

logger = Logger.get_logger("KitsBuilder")

# ---------------------------------------------------------------------------
# Native Instruments container + compression
# ---------------------------------------------------------------------------
#
# A Battery `.nbkt` is a tree of length-prefixed chunks:
#
#     <SEGMENT_LENGTH: le_u64>
#     <TAG: 4 bytes>            # "hsin", "DSIN", "4KIN", ...
#     <TYPE: le_u32>
#     <UNKNOWN: le_u32>         # always 1
#     <CHILD_LENGTH: le_u64>
#     <CHILD: CHILD_LENGTH bytes>
#     <DATA: remaining bytes>
#
# The kit document (cells + relative sample paths) is the single DSIN segment of
# TYPE 115, compressed with the FastLZ level-1 LZ77 variant used across NI
# formats (verified against monomadic/lz77, the reference implementation behind
# the ni-file project). `fastlz1_decompress` reproduces it byte-for-byte,
# including NI's zero-initialised sliding window.
#
# The clean kit display name and expansion live in a small uncompressed TYPE-108
# metadata segment; those strings are always intact and make a reliable key.
#
# ---------------------------------------------------------------------------
# Why fallbacks are needed for damaged path names
# ---------------------------------------------------------------------------
#
# Inside the compressed document each pad references its sample through a
# relative UTF-16LE path. NI's encoder, however, frequently emits individual
# characters of these path strings as LZ back-references that resolve to
# unrelated binary bytes, so a handful of characters per filename are *lost at
# the source*: the clean bytes exist nowhere in the file (verified by tracing the
# back-reference targets and by confirming no intact copy exists in any region).
# Decompression is provably correct; the data itself is lossy.
#
# Consequently, byte-exact recovery from extension-bearing sample paths can miss
# pads. For those cases, the parser falls back to the clean pad/cell labels that
# Battery stores nearby in the same decompressed document and emits them as the
# best available sample labels.

DSIN_TAG = b"DSIN"
COMPRESSED_DSIN_TYPE = 115
METADATA_DSIN_TYPE = 108
COMPRESSION_HEADER_LEN = 11
RECORD_MARKER = 0x04
RECORD_HEADER_LEN = 5
MAX_FILENAME_CHARS = 120
MAX_MARKER_DISTANCE = 280
FUZZY_TAIL_BYTES = 22000
EXTENSION_TOKENS = ("wav", "aiff", "aif", "flac", "ogg", "ncw")
DEFAULT_EXTENSION = "wav"
PATH_MARKER_WORDS = {
    "samples", "amples", "drums", "dru", "dru5", "loops", "one",
    "shots", "one shots", "one hots", "hihat", "percussion",
}
SAMPLE_NAME_TOKENS = (
    "kick", "clap", "snare", "closedhh", "openhh", "hh", "perc", "cymbal",
    "bass", "synth", "guitar", "crash", "sweep", "sfx", "piano", "pad",
    "combo", "chord", "shaker", "tom", "atmo", "revchoir", "vox", "noise",
    "click", "drill", "buzz", "metal", "rim", "blip", "pluck", "ride",
    "hit", "tambourine", "tambo", "taiko", "snap", "vocal", "percussion",
    "zap", "lofill", "drone", "lick", "wood", "rimstick", "drumfill",
    "keys", "vinyl", "sub", "lowtom", "metallic", "percroll",
    "sidestick", "snareroll", "organ", "stab", "agogo", "clave", "lead",
    "arp", "daouli", "darbuka", "wooden", "tonal", "tamb", "triangle",
    "asra", "dunnunba", "djembe", "kora", "ngoni", "bell", "balafon",
    "krin", "sangba", "calabash", "kenkeni", "midtom", "hitom", "hiconga",
    "brass", "bongo", "conga", "guiro", "splash", "flexitone", "cowbell",
    "woodblock", "drumroll", "impact", "ensemble", "rimshot", "cabasa",
    "swoop", "synthbass", "darkpiano", "wurlitzer", "cowbell", "mute",
)
TYPE_KIT_PREFIXES = {
    "claps": "Clap",
    "snares": "Snare",
    "snare": "Snare",
    "kicks": "Kick",
    "closedhh": "ClosedHH",
    "openhh": "OpenHH",
    "hihats": "HiHat",
    "hats": "HiHat",
    "percussion": "Perc",
    "perc": "Perc",
}

def fastlz1_decompress(src: bytes) -> bytes:
    """Decompress a Native-Instruments FastLZ level-1 stream (byte-exact).

    Faithful port of the FastLZ level-1 algorithm with NI's zero-initialised
    sliding window (references before the output start read as 0x00). Verified
    against monomadic/lz77, the reference implementation used by ni-file.
    """
    if not src:
        return b""
    op = bytearray()
    ip = 0
    n = len(src)
    ip_bound = n - 2
    ctrl = src[ip] & 31
    ip += 1
    while True:
        if ctrl >= 32:
            length = (ctrl >> 5) - 1
            ofs = (ctrl & 31) << 8
            ref = len(op) - ofs - 1
            if length == 7 - 1:
                if ip > ip_bound:
                    break
                length += src[ip]
                ip += 1
            ref -= src[ip]
            ip += 1
            length += 3
            for _ in range(length):
                op.append(op[ref] if 0 <= ref < len(op) else 0)
                ref += 1
        else:
            run = ctrl + 1
            op += src[ip:ip + run]
            ip += run
        if ip > ip_bound:
            break
        ctrl = src[ip]
        ip += 1
    return bytes(op)


def _iter_dsin(raw: bytes):
    for m in re.finditer(re.escape(DSIN_TAG), raw):
        p = m.start()
        if p < 8:
            continue
        try:
            seg_len = struct.unpack_from("<Q", raw, p - 8)[0]
            seg_type = struct.unpack_from("<I", raw, p + 4)[0]
            child_len = struct.unpack_from("<Q", raw, p + 12)[0]
        except struct.error:
            continue
        yield p, seg_type, seg_len, child_len


def find_compressed_kit(raw: bytes) -> bytes | None:
    """Locate the DSIN type-115 segment and return its decompressed bytes (or None)."""
    for p, seg_type, seg_len, child_len in _iter_dsin(raw):
        if seg_type != COMPRESSED_DSIN_TYPE:
            continue
        data_start = p + 20 + child_len
        if data_start + COMPRESSION_HEADER_LEN > len(raw):
            continue
        seg_end = p + 8 + seg_len
        if not (data_start < seg_end <= len(raw)):
            seg_end = len(raw)
        stream = raw[data_start + COMPRESSION_HEADER_LEN:seg_end]
        try:
            return fastlz1_decompress(stream)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FastLZ decompression failed at offset {p}: {e}")
            continue
    return None


def find_kit_name(raw: bytes, fallback: str) -> str:
    """Read the clean kit display name from the uncompressed TYPE-108 metadata."""
    for p, seg_type, seg_len, child_len in _iter_dsin(raw):
        if seg_type != METADATA_DSIN_TYPE or not (100 < seg_len < 8000):
            continue
        blob = raw[p + 20 + child_len:p + 8 + seg_len]
        m = re.search(rb"(?:[\x20-\x7e]\x00){3,}", blob)
        if m:
            return m.group().decode("utf-16le").strip()
    return fallback


def _find_kit_word(kit_name: str) -> str:
    word = re.sub(r"\s*Ki(t)?$", "", kit_name).strip()
    return word if word and " " not in word else ""


def _kit_name_tokens(kit_name: str) -> list[str]:
    """Return the compact token and significant words from the kit name for repair."""
    base = re.sub(r"\s*Ki(t)?$", "", kit_name, flags=re.I).strip()
    compact = base.replace(" ", "")
    words = re.findall(r"[A-Za-z0-9]{4,}", base)
    seen: set[str] = set()
    tokens: list[str] = []
    for t in [compact] + words:
        if len(t) >= 3 and t not in seen:
            seen.add(t)
            tokens.append(t)
    return tokens


def _repair_path_token(path: str, tokens: list[str]) -> str:
    """Repair corrupted kit name tokens in a sample path.

    Handles two failure modes caused by LZ back-reference corruption:
    - o↔0 substitution (e.g. '3onIt' → '30nIt')
    - missing/wrong leading characters (e.g. '4Life' → 'BLife', '80Great' → '0Great',
      'Funk' → 'unk' when the kit name word 'Funk' is a token)
    """
    has_ext = path.endswith(f".{DEFAULT_EXTENSION}")
    stem = path[:-len(f".{DEFAULT_EXTENSION}")] if has_ext else path
    for token in tokens:
        if len(token) < 3:
            continue
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", stem, re.I):
            continue  # already present
        # o↔0 substitution
        if any(c in "oO0" for c in token):
            loose = "".join(f"[o0]" if c.lower() in "o0" else re.escape(c) for c in token)
            m = re.search(rf"(?<![A-Za-z0-9]){loose}(?![A-Za-z0-9])", stem, re.I)
            if m:
                stem = stem[:m.start()] + token + stem[m.end():]
                break
        # Missing/wrong prefix: allow 0..cut chars before the token suffix
        for cut in range(1, min(4, len(token) - 1)):
            suffix = re.escape(token[cut:])
            m = re.search(
                rf"(?<![A-Za-z0-9])[A-Za-z0-9]{{0,{cut}}}{suffix}(?![A-Za-z0-9])",
                stem, re.I,
            )
            if m and stem[m.start():m.end()].lower() != token.lower():
                stem = stem[:m.start()] + token + stem[m.end():]
                break
        else:
            continue
        break
    return (stem + f".{DEFAULT_EXTENSION}") if has_ext else stem


def _compressed_segment_ranges(raw: bytes) -> list[tuple[int, int]]:
    """Return byte ranges of compressed TYPE-115 segments to skip during raw scanning."""
    ranges: list[tuple[int, int]] = []
    for p, seg_type, seg_len, child_len in _iter_dsin(raw):
        if seg_type == COMPRESSED_DSIN_TYPE:
            data_start = p + 20 + child_len
            seg_end = p + 8 + seg_len if p + 8 + seg_len <= len(raw) else len(raw)
            ranges.append((data_start, seg_end))
    return ranges


def extract_cell_labels_from_raw(raw: bytes) -> list[str]:
    """Scan uncompressed file regions for UTF-16LE cell labels.

    Battery stores cell/pad display labels as clean UTF-16LE strings in the
    uncompressed metadata regions of the .nbkt file, free of the LZ
    back-reference corruption that affects the TYPE-115 compressed document.
    """
    skip = _compressed_segment_ranges(raw)
    token_alt = "|".join(re.escape(t) for t in sorted(SAMPLE_NAME_TOKENS, key=len, reverse=True))
    labels: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", raw):
        pos = m.start()
        if any(s <= pos < e for s, e in skip):
            continue
        s = m.group().decode("utf-16le", errors="ignore").strip()
        if not (5 <= len(s) <= 80):
            continue
        if not re.search(r"[A-Za-z]", s):
            continue
        if re.search(r"[\\/<>|]", s):
            continue
        if not re.search(rf"(?i)(?<![A-Za-z])({token_alt})\b", s):
            continue
        label = f"{s}.{DEFAULT_EXTENSION}"
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _extract_bpm_values(decompressed: bytes) -> list[str]:
    """Return all clean BPM/pitch bracket values found in the decompressed data.

    Uses the strict UTF-16LE pattern so only genuinely uncorrupted brackets are returned.
    E.g. returns ['97', '83'] for a kit using those BPM values.
    """
    bpms: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", decompressed):
        s = m.group().decode("utf-16le", errors="ignore")
        for bm in re.findall(r"\[(\d{2,3})\]", s):
            if bm not in seen:
                seen.add(bm)
                bpms.append(bm)
    return bpms


def _repair_bracket(path: str, bpm_values: list[str]) -> str:
    """Fix corrupted BPM brackets such as '[ 7]' → '[97]' or '[8 ]' → '[84]'.

    Only repairs when there is a single BPM value known from the kit, or when the
    corrupted bracket has the right number of digits with only 1 character wrong.
    """
    if not bpm_values:
        return path

    def _fix(m: re.Match) -> str:
        inner = m.group(1)  # content inside brackets
        # Already valid digit string → no repair needed
        if re.fullmatch(r"\d+", inner):
            return m.group(0)
        digits = re.sub(r"[^\d]", "", inner)
        spaces = inner.count(" ") + inner.count("\x00")
        # Try to find a matching BPM
        for bpm in bpm_values:
            # Same length match: one corrupted char
            if len(inner) == len(bpm):
                # Count matching positions
                matches = sum(a == b for a, b in zip(inner, bpm))
                if matches >= len(bpm) - 1:
                    return f"[{bpm}]"
            # Digit-only content matches tail of bpm
            if digits and bpm.endswith(digits):
                return f"[{bpm}]"
        return m.group(0)

    return re.sub(r"\[([^\]]{1,5})\]", _fix, path)


def extract_cell_labels_fullscan(decompressed: bytes, kit_name: str) -> list[str]:
    """Scan the FULL decompressed data with a strict UTF-16LE pattern.

    Unlike the tail-only lane scan, this looks at the entire compressed document.
    The strict pattern (char + null byte both intact) finds the cleanest available
    version of each cell label, typically the first literal occurrence in the LZ
    stream before corruption from back-references accumulates.
    """
    token_alt = "|".join(re.escape(t) for t in sorted(SAMPLE_NAME_TOKENS, key=len, reverse=True))
    kit_tokens = _kit_name_tokens(kit_name)

    # Collect ALL strict UTF-16LE strings across the full data, keyed by first occurrence
    seen_stems: dict[str, tuple[int, str]] = {}
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", decompressed):
        raw_s = m.group().decode("utf-16le", errors="ignore").strip()
        if not (5 <= len(raw_s) <= 80):
            continue
        if re.search(r"[\\/<>|]", raw_s):
            continue
        # Clean noise prefix/suffix
        clean = re.sub(r"^[^A-Za-z0-9\[]+", "", raw_s)
        clean = re.sub(r"[^A-Za-z0-9 _\-\[\]#]+.*$", "", clean).strip()
        if len(clean) < 5:
            continue
        # Must have instrument token
        if not re.search(rf"(?i)(?<![A-Za-z])({token_alt})\b", clean):
            continue
        # Must contain a kit token
        has_kit = any(
            re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", clean)
            for t in kit_tokens
        )
        if not has_kit:
            continue
        stem = re.sub(rf"\.{DEFAULT_EXTENSION}$", "", clean, flags=re.I).strip()
        # Keep the FIRST (cleanest) occurrence only
        if stem not in seen_stems:
            seen_stems[stem] = (m.start(), clean)

    if not seen_stems:
        return []

    # Sort by offset so first occurrences come first
    ordered = sorted(seen_stems.values(), key=lambda x: x[0])
    paths = _dedupe_preserve_order(
        _number_duplicate_paths([f"{s}.{DEFAULT_EXTENSION}" for _, s in ordered])
    )
    return paths


def _read_filename(decompressed: bytes, start: int) -> str | None:
    chars: list[str] = []
    i = start
    noise = 0
    n = len(decompressed)
    while i + 1 < n and len(chars) < MAX_FILENAME_CHARS:
        lo = decompressed[i]
        i += 2
        if 0x20 <= lo < 0x7F:
            chars.append(chr(lo))
            noise = 0
            low = "".join(chars).lower()
            if any(low.endswith(ext) for ext in EXTENSION_TOKENS):
                return "".join(chars)
        else:
            chars.append("\x00")
            noise += 1
            if noise > 1:
                break
    return None


def _normalise(raw: str, kit_word: str) -> str | None:
    low = raw.lower()
    ext_pos, ext = -1, None
    for e in EXTENSION_TOKENS:
        idx = low.find(e)
        if idx != -1:
            ext_pos, ext = idx, e
            break
    if ext is None:
        return None
    body = raw[:ext_pos].rstrip("\x00")
    body = re.sub(r"[^A-Za-z0-9 _\-()]+$", "", body)
    name = re.sub(r"\s+", " ", body.replace("\x00", " ")).strip(" .")
    name = re.sub(r"^[^A-Za-z0-9]+", "", name)
    if kit_word and len(kit_word) >= 3:
        tail = re.escape(kit_word[1:])
        name = re.sub(rf"(?<![A-Za-z]){tail}(?![A-Za-z])", kit_word, name)
    if len(name) < 2 or not re.search(r"[A-Za-z]", name):
        return None
    return f"{name}.{ext.lower()}"


def _read_filename_relaxed(decompressed: bytes, start: int) -> str:
    chars: list[str] = []
    nulls = 0
    n = len(decompressed)
    while start + 1 < n and len(chars) < MAX_FILENAME_CHARS:
        b = decompressed[start]
        start += 2
        if b == 0:
            nulls += 1
            if nulls >= 2 and len(chars) >= 3:
                break
            continue
        nulls = 0
        chars.append(chr(b) if 0x20 <= b < 0x7F else "?")
    return "".join(chars).strip()


def _repair_kit_word(name: str, kit_word: str) -> str:
    if not kit_word or len(kit_word) < 4:
        return name
    fuzzy = r"[^A-Za-z0-9]?".join(re.escape(ch) for ch in kit_word)
    name = re.sub(fuzzy, kit_word, name, flags=re.I)
    tail = re.escape(kit_word[1:])
    return re.sub(rf"(?<![A-Za-z]){tail}(?![A-Za-z])", kit_word, name, flags=re.I)


def _normalise_fuzzy(raw: str, kit_word: str, kit_name: str) -> str | None:
    # Some factory kits have the filename intact but the extension bytes mangled
    # by back references, e.g. ".wav" becomes "w(v", "w$v" or ".aS".
    name = re.sub(
        r"(?i)(?:[ .>_-]*(?:w[^A-Za-z0-9\s]{0,5}(?:v|h|$)|\.w\S*|\.aS\S*|wSSS\S*)).*$",
        "",
        raw.replace("\x00", " "),
    )
    # Drop binary-prefix fragments when the real instrument token follows.
    token_alt = "|".join(re.escape(t) for t in SAMPLE_NAME_TOKENS)
    name = re.sub(rf"^.*?(?=(?<![A-Za-z])({token_alt})\b)", "", name, flags=re.I)
    name = name.replace("?", "").replace("@", "1")
    name = _repair_kit_word(name, kit_word)
    name = re.sub(r"[^A-Za-z0-9 _\-\[\]&()]+", "", name)
    name = re.sub(r"\s+", " ", name).strip(" ._-")

    if not (3 <= len(name) <= 70) or not re.search(r"[A-Za-z]", name):
        return None
    low = name.lower()
    kit_base = re.sub(r"\s*Ki(t)?$", "", kit_name).strip().lower()
    kit_last = kit_base.split()[-1] if kit_base.split() else ""
    if (not any(token in low for token in SAMPLE_NAME_TOKENS)
            and not (kit_last and kit_last[:4] in low.replace(" ", ""))):
        return None
    if low in {"drums", "loops", "one shots", "samples"}:
        return None
    if re.search(r"^(?:d2|sms|haker|mmsynth|evchoir|enhh)", low) or "iii" in low:
        return None
    return f"{name}.{DEFAULT_EXTENSION}"


def _kit_search_terms(kit_name: str) -> set[str]:
    base = re.sub(r"\s*Ki(t)?$", "", kit_name).strip()
    compact = base.replace(" ", "")
    terms = {base.lower(), compact.lower()} if base else set()
    words = re.findall(r"[A-Za-z0-9]+", base)
    if compact and len(compact) > 3:
        terms.add(compact[:3].lower())
    if "starwars" in compact.lower():
        terms.add("sw")
    if compact and len(compact) > 5:
        terms.add(compact[:5].lower())
    for word in words:
        if len(word) > 4:
            terms.add(word.lower())
    return {term for term in terms if term}


def _contains_kit_term(label: str, terms: set[str]) -> bool:
    low = label.lower()
    compact = low.replace(" ", "")
    compact_o = compact.replace("0", "o")
    return any(term in compact or term in low or term in compact_o for term in terms)


def _has_pitch_marker(label: str) -> bool:
    return bool(re.search(r"(?i)(?<![A-Za-z])(?:[A-G](?:#|b)?\d?|[A-G](?:#|b)?m)(?![A-Za-z])", label))


def _normalise_source_label(raw: str, kit_name: str) -> str | None:
    label = re.sub(r"(?i)(?:\.wav|\.aiff|\.aif|\.flac|\.ogg|\.ncw|\.w\S*).*$", "", raw)
    token_alt = "|".join(re.escape(token) for token in sorted(SAMPLE_NAME_TOKENS, key=len, reverse=True))
    label = re.sub(rf"(?i)^.*?(?=(?<![A-Za-z])({token_alt})\b)", "", label, count=1)
    label = label.replace("`", "").replace("+", "")
    label = re.sub(r"[^A-Za-z0-9 _\-\[\]#&()]+", " ", label)
    label = re.sub(rf"^[A-Z]{{1,3}}(?=(?i:({token_alt})\b))", "", label)
    label = re.sub(rf"^[a-z](?=(?i:({token_alt})\b))", "", label)
    label = re.sub(r"\s+", " ", label).strip(" ._-")
    if not (3 <= len(label) <= 70) or not re.search(r"[A-Za-z]", label):
        return None
    low = label.lower()
    if low in {"drums", "loops", "one shots", "samples", "smls", "dru"}:
        return None
    if any(noise in low for noise in ("hhh", "000", "111", "jjj", "kkk", "lll", "&&", "www")):
        return None
    token_match = re.search(rf"(?i)(?<![A-Za-z])({token_alt})\b", label)
    if not token_match:
        return None
    terms = _kit_search_terms(kit_name)
    starts_with_token = token_match.start() == 0
    if terms and not _contains_kit_term(label, terms) and not (starts_with_token and _has_pitch_marker(label)):
        return None
    return f"{label}.{DEFAULT_EXTENSION}"


def extract_sample_paths_from_labels(decompressed: bytes, kit_name: str) -> list[str]:
    tail_start = max(0, len(decompressed) - FUZZY_TAIL_BYTES)
    entries = sorted(_iter_lane_strings(decompressed, tail_start))
    raw_entries: list[tuple[int, str]] = []
    for i, (offset, raw) in enumerate(entries):
        combined = raw
        if "[" in raw and "]" not in raw:
            for next_offset, next_raw in entries[i + 1:i + 4]:
                if next_offset % 2 == offset % 2 and 0 < next_offset - offset < 80:
                    combined += next_raw
                    if "]" in next_raw:
                        break
        raw_entries.append((offset, combined))

    paths: list[str] = []
    for _, raw in raw_entries:
        path = _normalise_source_label(raw, kit_name)
        if path:
            paths.append(path)

    counts: dict[str, int] = {}
    for path in paths:
        counts[path] = counts.get(path, 0) + 1
    occurrences: dict[str, int] = {}
    numbered: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if counts[path] > 1:
            stem = path[:-len(f".{DEFAULT_EXTENSION}")]
            occurrences[path] = occurrences.get(path, 0) + 1
            path = f"{stem} {occurrences[path]}.{DEFAULT_EXTENSION}"
        if path not in seen:
            seen.add(path)
            numbered.append(path)
    return numbered


def _sample_token_count(paths: list[str]) -> int:
    token_alt = "|".join(re.escape(token) for token in sorted(SAMPLE_NAME_TOKENS, key=len, reverse=True))
    return sum(1 for path in paths if re.search(rf"(?i)(?<![A-Za-z])({token_alt})\b", path))


def _dedupe_preserve_order(paths: list[str], *, keep_duplicates: bool = False) -> list[str]:
    if keep_duplicates:
        return paths
    result: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _iter_lane_strings(decompressed: bytes, tail_start: int, min_len: int = 3):
    n = len(decompressed)
    for parity in (0, 1):
        lows = bytes(decompressed[j] for j in range(parity, n - 1, 2))
        base = max(0, (tail_start - parity + 1) // 2)
        for m in re.finditer(rb"[ -~]{%d,}" % min_len, lows[base:]):
            yield parity + (base + m.start()) * 2, m.group().decode("latin1", "replace")


def _clean_source_fragment(raw: str) -> str:
    fragment = raw.replace("\x00", " ")
    fragment = fragment.replace("?", " ").replace("`", " ").replace("+", " ")
    fragment = re.sub(r"[^A-Za-z0-9 _\-\[\]#&().]+", " ", fragment)
    fragment = re.sub(r"\s+", " ", fragment).strip(" ._-")
    return fragment


def _is_path_marker(raw: str) -> bool:
    fragment = _clean_source_fragment(raw).lower()
    return fragment in PATH_MARKER_WORDS or fragment.endswith("/one shots")


def _is_source_noise(raw: str) -> bool:
    fragment = _clean_source_fragment(raw)
    if not fragment or len(fragment) <= 1:
        return True
    if _is_path_marker(fragment):
        return True
    return bool(re.fullmatch(r"[A-ZDFGm]+|\d+", fragment))


def _source_fragment_has_kit_term(fragment: str, kit_name: str) -> bool:
    return _contains_kit_term(fragment, _kit_search_terms(kit_name))


def _is_kit_suffix_stem(fragment: str, kit_name: str) -> bool:
    terms = _kit_search_terms(kit_name)
    parts = [part for part in re.findall(r"[A-Za-z0-9]+", fragment.lower()) if not part.isdigit()]
    compact = "".join(parts)
    return bool(compact and any(compact == term.replace(" ", "") for term in terms))


def _normalise_source_stream_name(name: str) -> str | None:
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    name = re.sub(r"^[a-z]\d(?=[A-Z][a-z])", "", name)
    name = re.sub(r"^[A-Z](?=[A-Z][a-z])", "", name)
    name = re.sub(r"^[a-z](?=[A-Z]{2,}\b)", "", name)
    # Strip 1-2 leading digits that precede a capital letter — these are path-byte noise
    # (e.g. "75Snare" → "Snare") but preserve deliberate 3-digit prefixes like "808".
    name = re.sub(r"^\d{1,2}(?=[A-Z])", "", name)
    name = re.sub(r"\[\s+", "[", name)
    name = re.sub(r"\s+\]", "]", name)
    name = name.replace("[ ", "[")
    if not (3 <= len(name) <= 90) or not re.search(r"[A-Za-z]", name):
        return None
    if _is_path_marker(name.lower()):
        return None
    return f"{name}.{DEFAULT_EXTENSION}"


def _restore_token_prefix(fragment: str) -> str:
    """If a fragment starts lowercase, try to identify its missing capital prefix.

    LZ back-references sometimes corrupt the first byte of an instrument token
    (e.g. 'ass' instead of 'Bass', 'haker' instead of 'Shaker').  When the
    fragment (lowercased) is a known suffix of a SAMPLE_NAME_TOKEN we prepend
    the missing prefix character(s).
    """
    if not fragment or fragment[0].isupper() or fragment[0].isdigit() or fragment[0] in "[]":
        return fragment
    low = fragment.lower()
    best: tuple[int, str] = (0, fragment)
    for token in SAMPLE_NAME_TOKENS:
        for match_len in range(3, min(len(fragment) + 1, len(token))):
            if token.endswith(low[:match_len]):
                prefix = token[:-match_len]
                if len(prefix) == 1:
                    candidate = prefix.upper() + fragment
                    if match_len > best[0]:
                        best = (match_len, candidate)
                break
    return best[1]


def _build_source_stream_name(fragments: list[str], ext_stem: str, kit_name: str) -> str | None:
    useful: list[str] = []
    for raw in fragments:
        fragment = _clean_source_fragment(raw)
        fragment = _restore_token_prefix(fragment)
        if _is_source_noise(fragment):
            continue
        if useful and useful[-1].lower() == fragment.lower():
            continue
        useful.append(fragment)

    stem = _clean_source_fragment(ext_stem)
    if stem and (not useful or useful[-1].lower() != stem.lower()):
        useful.append(stem)
    if not useful:
        return None

    if stem and not re.fullmatch(r"(?i)%s" % "|".join(EXTENSION_TOKENS), stem):
        if len(stem) <= 3 and stem.islower() and len(useful) >= 2:
            name = useful[-2]
        elif stem.startswith("]") and len(useful) >= 2:
            name = useful[-2] + stem
        elif len(useful) >= 2 and useful[-2].endswith("["):
            name = useful[-2] + stem
        elif (
            _is_kit_suffix_stem(stem, kit_name)
            and len(useful) >= 2
            and useful[-2].lower() not in stem.lower()
        ):
            name = f"{useful[-2]} {stem}"
        elif stem and stem[0].islower() and len(useful) >= 2 and "[" in useful[-2]:
            name = useful[-2] + stem
        else:
            name = stem
    elif len(useful) >= 2 and useful[-1].startswith("]"):
        # Bracket tail: use last 3 elements but only prepend useful[-3] when it
        # is NOT already the first word of useful[-2] (otherwise the folder name
        # is duplicating the start of the filename, e.g. "Lick" + "Lick Guitar[1").
        if len(useful) >= 3:
            prev_first = useful[-2].split("[")[0].split()[0] if useful[-2] else ""
            if useful[-3].lower() != prev_first.lower():
                name = f"{useful[-3]} {useful[-2]}{useful[-1]}"
            else:
                name = f"{useful[-2]}{useful[-1]}"
        else:
            name = useful[-2] + useful[-1]
        name = re.sub(r"\s+", " ", name).strip()
    elif len(useful) >= 2 and useful[-2].endswith("["):
        name = useful[-2] + useful[-1]
    elif len(useful) >= 3 and useful[-2].endswith("["):
        name = useful[-3] + " " + useful[-2] + useful[-1]
    elif (
        len(useful) >= 2
        and _is_kit_suffix_stem(useful[-1], kit_name)
        and len(useful[-1].split()) <= 2
    ):
        name = f"{useful[-2]} {useful[-1]}"
    else:
        name = useful[-1]

    return _normalise_source_stream_name(name)


def _number_duplicate_paths(paths: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for path in paths:
        counts[path] = counts.get(path, 0) + 1
    reserved = {path for path in paths if counts[path] == 1}
    occurrences: dict[str, int] = {}
    numbered: list[str] = []
    for path in paths:
        if counts[path] > 1:
            stem = path[:-len(f".{DEFAULT_EXTENSION}")]
            occurrences[path] = occurrences.get(path, 0) + 1
            index = occurrences[path]
            candidate = f"{stem} {index}.{DEFAULT_EXTENSION}"
            while candidate in reserved:
                index += 1
                candidate = f"{stem} {index}.{DEFAULT_EXTENSION}"
            occurrences[path] = index
            path = candidate
        reserved.add(path)
        numbered.append(path)
    return numbered


def extract_sample_paths_from_source_stream(decompressed: bytes, kit_name: str) -> list[str]:
    """Extract sample filenames from the DSIN string stream, like the groups parser.

    Battery kits store each source path as UTF-16-ish low-byte string fragments:
    path markers such as "Samples"/"Drums", optional folder fragments, then the
    filename stem and extension. The extension is often split into a standalone
    "wav" fragment, so this parser works over adjacent source fragments instead
    of relying on instrument names.
    """
    tail_start = max(0, len(decompressed) - FUZZY_TAIL_BYTES)
    entries = sorted(_iter_lane_strings(decompressed, tail_start, min_len=1))
    paths: list[str] = []
    fragments: list[str] = []

    for _, raw in entries:
        fragment = _clean_source_fragment(raw)
        if _is_path_marker(fragment):
            fragments = []
            continue

        m = re.search(r"(?i)(?:\.?\b(?:wav|aiff|aif|flac|ogg|ncw)\b)", fragment)
        if m:
            ext_stem = fragment[:m.start()]
            path = _build_source_stream_name(fragments, ext_stem, kit_name)
            if path:
                paths.append(path)
            fragments = []
            continue

        fragments.append(raw)
        if len(fragments) > 10:
            fragments = fragments[-10:]

    return _dedupe_preserve_order(_number_duplicate_paths(paths))


def extract_sample_paths_fuzzy(decompressed: bytes, kit_name: str) -> list[str]:
    """Fallback for records whose extension bytes are corrupted or lane-shifted."""
    n = len(decompressed)
    tail_start = max(0, n - FUZZY_TAIL_BYTES)
    kit_word = _find_kit_word(kit_name)
    paths: list[str] = []

    for p in range(tail_start, n):
        if decompressed[p] != RECORD_MARKER:
            continue
        for start in (p + RECORD_HEADER_LEN, p + RECORD_HEADER_LEN + 1):
            raw = _read_filename_relaxed(decompressed, start)
            if not re.search(r"(?i)(w[^A-Za-z0-9\s]{0,5}v|\.w|\.aS|wSSS|w\s*,\s*vh)", raw):
                continue
            name = _normalise_fuzzy(raw, kit_word, kit_name)
            if name:
                paths.append(name)

    paths = _dedupe_preserve_order(paths)
    if len(paths) >= 4:
        return paths
    type_paths = extract_type_kit_labels(decompressed, kit_name)
    return type_paths if len(type_paths) > len(paths) else paths


def _kit_type_prefix(kit_name: str) -> str | None:
    low = kit_name.lower().replace(" ", "")
    for key, prefix in TYPE_KIT_PREFIXES.items():
        if key in low:
            return prefix
    return None


def extract_type_kit_labels(decompressed: bytes, kit_name: str) -> list[str]:
    """Last-resort label extraction for one-instrument kits with lost extensions."""
    prefix = _kit_type_prefix(kit_name)
    if not prefix:
        return []

    tail_start = max(0, len(decompressed) - 9000)
    paths: list[str] = []
    seen: set[str] = set()
    reject = {
        "dru", "drums", "vh", "w,h", "samples", "smls", "sfo", "kit", "true",
        "school", "trill", "rays", "all", "snr", "sn#r", "ri", "rim",
    }
    for _, raw in _iter_lane_strings(decompressed, tail_start):
        label = raw
        label = re.sub(r"(?i)(?:w[^A-Za-z0-9\s]{0,5}(?:v|h|$)|\.w\S*|\.aS\S*).*$", "", label)
        label = re.sub(r"(?i)(?:SFO|hS_|a!t_a<l|Dru@e|Dru|Smls|Sn#r|\\Ri)", " ", label)
        label = label.replace("?", "").replace(":", "").replace("+", "").replace("[", "")
        label = re.sub(r"[^A-Za-z0-9 _\-&]+", "", label)
        label = re.sub(r"\s+", " ", label).strip(" ._-")
        low = label.lower()
        if not (3 <= len(label) <= 38) or low in reject or low.isdigit():
            continue
        if not re.search(r"[A-Za-z]", label):
            continue
        if low[0].isdigit() or (prefix == "Clap" and "hh" in low):
            continue
        if any(part in low for part in ("hhh", "000", "111", "aaa", "jjj", "kkk", "lll", "&&", "www")):
            continue
        if re.fullmatch(r"[A-Z]{2,}[a-z]?", label):
            continue
        if prefix.lower() not in low:
            label = f"{prefix} {label}"
        path = f"{label}.{DEFAULT_EXTENSION}"
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def extract_sample_paths_heuristic(decompressed: bytes, kit_name: str) -> list[str]:
    """Best-effort filename recovery directly from the (lossy) compressed payload."""
    n = len(decompressed)
    kit_word = _find_kit_word(kit_name)
    results: list[tuple[int, str]] = []
    seen: set[int] = set()
    for parity in (0, 1):
        lows = bytes(decompressed[j] for j in range(parity, n - 1, 2))
        offsets = [parity + i * 2 for i in range(len(lows))]
        for ext in EXTENSION_TOKENS:
            for m in re.finditer(re.escape(ext.encode()), lows, re.I):
                ext_byte = offsets[m.start()]
                for delta in range(RECORD_HEADER_LEN + 1, MAX_MARKER_DISTANCE):
                    marker = ext_byte - delta
                    if marker < 0:
                        break
                    if decompressed[marker] != RECORD_MARKER:
                        continue
                    start = marker + RECORD_HEADER_LEN
                    raw = _read_filename(decompressed, start)
                    if not raw:
                        continue
                    low = raw.lower()
                    rel = next((low.find(e) for e in EXTENSION_TOKENS if e in low), -1)
                    if rel < 0 or abs(start + rel * 2 - ext_byte) > 2:
                        continue
                    if start not in seen:
                        seen.add(start)
                        results.append((start, raw))
                    break
    results.sort()
    names: list[str] = []
    last = None
    for _, raw in results:
        name = _normalise(raw, kit_word)
        if name and name != last:
            names.append(name)
            last = name
    return names


def extract_sample_paths(decompressed: bytes, kit_name: str,
                         raw: bytes | None = None) -> tuple[list[str], bool]:
    """Return (sample filenames, verified) for the kit."""
    raw_labels = extract_cell_labels_from_raw(raw) if raw is not None else []

    # Strict UTF-16LE scan across the FULL decompressed data —
    # finds the cleanest (first literal) occurrence of each pad label.
    fullscan_labels = extract_cell_labels_fullscan(decompressed, kit_name)

    # Collect clean BPM values from the full scan to repair corrupted brackets
    bpm_values = _extract_bpm_values(decompressed)

    stream_paths = extract_sample_paths_from_source_stream(decompressed, kit_name)
    paths = extract_sample_paths_heuristic(decompressed, kit_name)
    fuzzy_paths = extract_sample_paths_fuzzy(decompressed, kit_name)
    label_paths = extract_sample_paths_from_labels(decompressed, kit_name)

    # Apply token repair + BPM bracket repair to all candidates
    tokens = _kit_name_tokens(kit_name)

    def _repaired_deduped(lst: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for p in lst:
            p = _repair_path_token(p, tokens)
            p = _repair_bracket(p, bpm_values)
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    stream_paths = _repaired_deduped(stream_paths)
    paths = _repaired_deduped(paths)
    fuzzy_paths = _repaired_deduped(fuzzy_paths)
    label_paths = _repaired_deduped(label_paths)

    # Raw labels from uncompressed regions are corruption-free; prefer when exact.
    if len(raw_labels) in (16, 32):
        return raw_labels, True

    # Fullscan labels come from strict UTF-16LE — prefer when exact grid size.
    if len(fullscan_labels) in (16, 32):
        return fullscan_labels, False

    decompressed_candidates = (stream_paths, paths, fuzzy_paths, label_paths)
    exact_candidates = [c for c in decompressed_candidates if len(c) in (16, 32)]
    if exact_candidates:
        if stream_paths in exact_candidates:
            return stream_paths, False
        return max(exact_candidates, key=_sample_token_count), False

    # If fullscan found something useful, prefer it over noisy decompressed results
    if len(fullscan_labels) >= 4:
        return fullscan_labels, False
    if len(raw_labels) >= 4:
        return raw_labels, False

    best = max(decompressed_candidates, key=len)
    return best if best else paths, False


def classify_samples(paths: list[str]) -> list[dict]:
    result = [{"type": "sample", "pad": i, "path": p} for i, p in enumerate(paths, 1)]
    if len(result) > 16:
        logger.warning(f"kit has {len(result)} pads (more than 16).")
    return result


def find_nbkt_files(folder_in: str) -> list[str]:
    nbkt_files = []
    for root, _, files in os.walk(folder_in):
        for file in files:
            if file.lower().endswith(".nbkt"):
                nbkt_files.append(os.path.join(root, file))
    return nbkt_files


def clear_parsed_folder(output_folder: str):
    parsed_folder = os.path.join(output_folder, "parsed")
    if os.path.exists(parsed_folder):
        shutil.rmtree(parsed_folder)
    os.makedirs(parsed_folder, exist_ok=True)


def _find_companion_mxgrp(nbkt_path: str) -> str | None:
    """Return the path of a Maschine .mxgrp companion for this Battery kit, if one exists.

    Battery kits and Maschine groups from the same NI expansion often ship side-by-side:
      .../Library/Sounds/Battery Kits/KitName.nbkt
      .../Library/Groups/Kits/KitName.mxgrp

    The Maschine group stores sample paths as clean ASCII strings — using it avoids the
    LZ back-reference corruption that plagues the Battery compressed document.
    """
    kit_name = os.path.splitext(os.path.basename(nbkt_path))[0]
    target = kit_name + ".mxgrp"
    nbkt_dir = os.path.dirname(os.path.abspath(nbkt_path))
    parent1 = os.path.dirname(nbkt_dir)   # e.g. Sounds/
    parent2 = os.path.dirname(parent1)    # e.g. Library/
    parent3 = os.path.dirname(parent2)

    candidates = [
        os.path.join(parent2, "Groups", "Kits", target),
        os.path.join(parent2, "Groups", target),
        os.path.join(parent3, "Groups", "Kits", target),
        os.path.join(parent3, "Groups", target),
        os.path.join(parent1, target),
        os.path.join(parent2, target),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _extract_from_mxgrp(mxgrp_path: str, kit_name: str) -> list[str]:
    """Extract clean pad sample filenames from a companion Maschine .mxgrp file."""
    try:
        from processors.groups.build_groups_json import (
            try_decompress, extract_clean_strings, post_process,
            find_expansion_name, classify_samples,
        )
        with open(mxgrp_path, "rb") as f:
            data = try_decompress(f.read())
        filtered = post_process(extract_clean_strings(data))
        expansion = find_expansion_name(filtered)
        if expansion is None:
            return []
        samples = classify_samples(filtered, kit_name, expansion)
        paths: list[str] = []
        for s in samples:
            raw_path = s.get("paths") or s.get("path", "")
            if isinstance(raw_path, list):
                raw_path = raw_path[0] if raw_path else ""
            fname = os.path.basename(raw_path) if raw_path else ""
            if fname:
                paths.append(fname)
        return paths
    except Exception as e:
        logger.debug(f"mxgrp extraction failed for {mxgrp_path}: {e}")
        return []


def process_nbkt_file(input_file: str, output_folder: str, generate_txt: bool = True) -> dict | None:
    with open(input_file, "rb") as f:
        raw_data = f.read()

    kit_file_name = os.path.splitext(os.path.basename(input_file))[0]

    decompressed = find_compressed_kit(raw_data)
    if decompressed is None:
        logger.warning(f"No compressed kit segment found in: {kit_file_name}")
        return None

    kit_name = find_kit_name(raw_data, kit_file_name)

    # Try companion .mxgrp first — it stores paths as clean ASCII (groups-parser approach)
    mxgrp_path = _find_companion_mxgrp(input_file)
    mxgrp_paths: list[str] = []
    if mxgrp_path:
        mxgrp_paths = _extract_from_mxgrp(mxgrp_path, kit_name)
        if mxgrp_paths:
            logger.debug(f"Using companion mxgrp for {kit_file_name}: {len(mxgrp_paths)} pads")

    if len(mxgrp_paths) in (16, 32):
        sample_paths = mxgrp_paths
        verified = True
    else:
        sample_paths, verified = extract_sample_paths(decompressed, kit_name, raw_data)
    sample_data = classify_samples(sample_paths)

    if generate_txt:
        parsed_folder = os.path.join(output_folder, "parsed")
        os.makedirs(parsed_folder, exist_ok=True)
        output_filepath = ensure_unique_path(parsed_folder, f"{sanitize(kit_file_name)}.txt")
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(sample_paths))
    else:
        output_filepath = None

    kit_info = {
        "kit": kit_name.strip(),
        "source": "Battery",
        "verified": verified,
        "path": os.path.abspath(input_file).replace("\\", "/"),
        "samples": sample_data,
        "txt_file": output_filepath,
    }
    logger.info(f"Processed kit: {kit_name}, samples: {len(sample_data)}"
                f"{' (verified)' if verified else ' (heuristic)'}")
    return kit_info


class KitsJsonBuilder:
    def __init__(self, input_folder: str, output_folder: str,
                 combined_json_name: str = "all_kits.json", generate_txt: bool = True):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.combined_json_name = combined_json_name
        self.generate_txt = generate_txt

    def run(self, worker_instance=None):
        try:
            if not os.path.isdir(self.output_folder):
                os.makedirs(self.output_folder)
            clear_parsed_folder(self.output_folder)

            nbkt_files = find_nbkt_files(self.input_folder)
            logger.info(f"Found {len(nbkt_files)} .nbkt files to process.")

            all_kits = []
            for nbkt_path in nbkt_files:
                if worker_instance and worker_instance.cancel_requested():
                    logger.info("Kits JSON build cancelled by user.")
                    return 1
                try:
                    kit_data = process_nbkt_file(nbkt_path, self.output_folder,
                                                 generate_txt=self.generate_txt)
                    if not kit_data:
                        continue
                    if not kit_data["samples"]:
                        logger.warning(f"Skipped kit with no samples: {kit_data['kit']}")
                        continue
                    all_kits.append(kit_data)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error processing '{nbkt_path}': {e}")

            combined_json_path = os.path.join(self.output_folder, self.combined_json_name)
            with open(combined_json_path, "w", encoding="utf-8") as f:
                json.dump(all_kits, f, indent=2, ensure_ascii=False)
            logger.info(f"All kits saved to {combined_json_path}")
            return 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error building kits JSON: {e}")
            return 1


def main(input_folder: str, output_folder: str,
         combined_json_name: str = "all_kits.json", generate_txt: bool = True):
    builder = KitsJsonBuilder(input_folder, output_folder, combined_json_name, generate_txt)
    sys.exit(builder.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Builds a JSON file of Native Instruments Battery kits.")
    parser.add_argument("input_folder", help="Path to the input folder containing .nbkt files.")
    parser.add_argument("output_folder", help="Path to the output folder for the JSON and parsed text files.")
    parser.add_argument("--combined_json_name", default="all_kits.json",
                        help="Name of the combined JSON file (default: all_kits.json).")
    parser.add_argument("--generate_txt", type=lambda x: x.lower() == "true", default=True,
                        help="Generate individual parsed text files for each kit (default: true).")
    args = parser.parse_args()

    if not os.path.isdir(args.input_folder):
        logger.error(f"Error: Input folder '{args.input_folder}' does not exist or is not a directory.")
        sys.exit(1)
    try:
        Path(args.output_folder).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error: Could not create output folder '{args.output_folder}': {e}")
        sys.exit(1)
    try:
        main(args.input_folder, args.output_folder, args.combined_json_name, args.generate_txt)
    except SystemExit as e:
        sys.exit(e.code)
