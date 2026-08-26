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
# TYPE 115. Its data slice begins with an 11-byte compression header; the
# FastLZ stream starts immediately after it.
#
# The compressor is the FastLZ level-1 byte-aligned LZ77, with one Native
# Instruments deviation: the sliding window is *zero-initialised*, so a match
# may legally reference bytes "before" the start of the output, which read as
# 0x00 (vanilla FastLZ instead aborts on such a reference). `fastlz1_decompress`
# below implements exactly that, and has been verified byte-for-byte against a C
# port of FastLZ's `fastlz1_decompress` modified for the zero-window rule.
#
# The opcode grammar (matching FastLZ level 1 precisely):
#   * ctrl = first_byte & 31  (the top 3 bits of byte 0 are the level tag, == 1)
#   * if ctrl >= 32: a match.  len = (ctrl >> 5) - 1; if len == 6, len += next
#     byte. distance = (ctrl & 31) << 8; ref = op - distance - 1 - next_byte;
#     copy len + 3 bytes (overlapping).
#   * else: a literal run of ctrl + 1 bytes.
#   * after each op, read the next ctrl byte until the input is exhausted.

DSIN_TAG = b"DSIN"
COMPRESSED_DSIN_TYPE = 115
COMPRESSION_HEADER_LEN = 11
SAMPLES_ANCHOR = "Samples"
RECORD_MARKER = 0x04           # precedes the filename inside a "Samples" record
AUDIO_EXTENSIONS = (".wav", ".aiff", ".aif", ".flac", ".ogg", ".ncw")


def fastlz1_decompress(src: bytes) -> bytes:
    """Decompress a Native-Instruments FastLZ level-1 stream (byte-exact).

    Faithful port of FastLZ `fastlz1_decompress` with NI's zero-initialised
    sliding window: references that fall before the start of the output yield
    0x00 rather than aborting. Produces output identical to the reference C
    implementation for every byte.
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


def find_compressed_kit(raw: bytes) -> bytes | None:
    """Locate the DSIN type-115 segment and return its decompressed bytes (or None)."""
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


def _read_filename(out: bytes, start: int) -> str:
    """Read a filename from byte offset `start`, striding by 2 (same byte lane).

    Works for both UTF-16LE (start even, chars in lo bytes) and UTF-16BE (start
    odd, chars in hi bytes). Stops at the first non-printable byte or when an
    audio extension completes.
    """
    chars: list[str] = []
    i = start
    while i + 1 < len(out) and len(chars) < 120:
        b = out[i]
        i += 2
        if 0x20 <= b < 0x7F:
            chars.append(chr(b))
            low = "".join(chars).lower()
            if any(low.endswith(ext) for ext in AUDIO_EXTENSIONS):
                break
        else:
            break
    return "".join(chars)


def extract_sample_paths(decompressed: bytes) -> list[str]:
    """Extract sample filenames from the decompressed Battery kit document.

    Two marker variants are handled:
    - LE (chars in even/lo bytes): 6-byte marker \x00\x04\x00\x00\x00\x00,
      filename read from even offset.
    - BE (chars in odd/hi bytes): \x04 at even offset followed by a null unit
      (but NOT preceded by \x00, to avoid overlap with the LE marker), filename
      read from the odd byte of the unit immediately after the null unit.
    Consecutive duplicates are removed.
    """
    n = len(decompressed)
    records: list[tuple[int, int]] = []  # (file_offset, read_start)

    # LE marker
    LE_MARKER = b"\x00\x04\x00\x00\x00\x00"
    for m in re.finditer(re.escape(LE_MARKER), decompressed):
        records.append((m.start(), m.end()))  # read from even offset

    # BE marker: \x04 at even position P where the 6 bytes starting at P-1 do NOT form
    # the LE marker (to avoid double-counting), followed by a null unit at P+2..P+3.
    LE_MARKER = b"\x00\x04\x00\x00\x00\x00"
    for p in range(0, n - 5, 2):
        if (decompressed[p] == 0x04
                and not (p > 0 and decompressed[p - 1:p + 5] == LE_MARKER)
                and decompressed[p + 2] == 0x00 and decompressed[p + 3] == 0x00):
            records.append((p, p + 5))  # read from odd byte of filename's first unit

    records.sort()

    names: list[str] = []
    last = None
    for _, read_start in records:
        raw_name = _read_filename(decompressed, read_start)
        low = raw_name.lower()
        end = next((low.find(ext) + len(ext) for ext in AUDIO_EXTENSIONS if ext in low), -1)
        if end == -1:
            continue
        name = re.sub(r"^[^A-Za-z0-9]+", "", raw_name[:end].strip())
        if len(name) > 4 and name != last:
            names.append(name)
            last = name
    return names


def find_kit_name(decompressed: bytes, fallback: str) -> str:
    m = re.search(rb"(?:[\x20-\x7e]\x00){4,}", decompressed)
    return m.group().decode("utf-16le").strip() if m else fallback


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


def process_nbkt_file(input_file: str, output_folder: str, generate_txt: bool = True) -> dict | None:
    with open(input_file, "rb") as f:
        raw_data = f.read()

    kit_file_name = os.path.splitext(os.path.basename(input_file))[0]

    decompressed = find_compressed_kit(raw_data)
    if decompressed is None:
        logger.warning(f"No compressed kit segment found in: {kit_file_name}")
        return None

    kit_name = find_kit_name(decompressed, kit_file_name)
    sample_paths = extract_sample_paths(decompressed)
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
        "path": os.path.abspath(input_file).replace("\\", "/"),
        "samples": sample_data,
        "txt_file": output_filepath,
    }
    logger.info(f"Processed kit: {kit_name}, samples: {len(sample_data)}")
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
