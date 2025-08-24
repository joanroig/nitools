import json
import os
import re
import shutil
import sys
import zlib

from utils.constants import LOGS_PATH
from utils.logger import Logger

logger = Logger.get_logger("GroupsBuilder")

# --- Config ---
MERGED_EXPANSIONS = {
    "Maschine 2": "Maschine 2 Factory Library",
    "Maschine 2 Factory": "Maschine 2 Factory Library",
    "Maschine 2 Factory Library": "Maschine 2 Factory Library"
}

EXCLUDED_EXPANSIONS = {}  # Add problematic expansions to exclude here, e.g. {"Maschine 2": "Maschine 2 Factory Library"}


def try_decompress(data: bytes) -> bytes:
    """Try to decompress data using zlib. Return original data on failure."""
    try:
        return zlib.decompress(data)
    except zlib.error:
        return data


def extract_clean_strings(data: bytes, min_length: int = 4) -> list[str]:
    """Extract ASCII strings from data, filtering out noisy ones."""
    pattern = re.compile(rb'[\x20-\x7E]{%d,}' % min_length)
    matches = pattern.findall(data)

    def is_clean(s: bytes) -> bool:
        text = s.decode('ascii', errors='ignore')
        special_chars = sum(not c.isalnum() and c not in ' _-.:/@' for c in text)
        return (special_chars / len(text)) <= 0.3

    return [m.decode('ascii', errors='ignore') for m in matches if is_clean(m)]


def post_process(lines: list[str]) -> list[str]:
    """Filter out noise and keep only lines after the serialization marker."""
    cleaned = []
    ignore_pattern = re.compile(r'^.{3}\?.{3}\?$')

    for line in lines:
        if ignore_pattern.fullmatch(line):
            continue
        if 'NI::MASCHINE::DATA::' in line and 'PluginHost' not in line:
            continue
        cleaned.append(line)

    for i, line in enumerate(cleaned):
        if 'serialization::archive' in line:
            return cleaned[i:]
    return cleaned  # fallback

def is_garbage_line(line: str) -> bool:
    allowed_chars = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-[]()")
    # Return True if line contains any disallowed character or line length is exactly 4
    return len(line) == 4 or any(c not in allowed_chars for c in line)

def find_expansion_name(lines: list[str], folder_two_levels_up: str = None) -> str:
    """Extract the ExpansionName from lines, with fallback to folder_two_levels_up or 'UnknownExpansion'."""
    for i, line in enumerate(lines):
        if "serialization::archive" in line:
            if i + 2 < len(lines):
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()
                if line1 == line2:
                    return line1
                else:
                    logger.warning(f"Lines after 'serialization::archive' differ: '{line1}' != '{line2}'")
                    if folder_two_levels_up:
                        folder_name = os.path.basename(folder_two_levels_up).strip()
                        if folder_name.endswith("Library"):
                            folder_name = folder_name[:-len("Library")].strip()
                        return folder_name
                    else:
                        return "UnknownExpansion"
            else:
                return "UnknownExpansion"
    return None


def classify_samples(lines: list[str], group_name: str, expansion_name: str) -> list[dict]:
    """Group .wav files into multisamples or samples, assign pad numbers consecutively (1..∞), and clean paths.
       Now supports split sample paths across multiple lines.
       Also removes consecutive duplicate sample paths (after cleaning).
       Warns if more than 16 pads are detected.
    """

    # --- Preprocess: merge split sample paths ---
    merged_lines = []
    skip_next = False
    for i in range(len(lines)):
        if skip_next:
            skip_next = False
            continue

        line = lines[i]
        if (
            i + 1 < len(lines)
            and not line.lower().endswith(".wav")
            and lines[i + 1].lower().endswith(".wav")
        ):
            stripped = line.lstrip()
            if stripped.startswith("Samples/") or stripped.startswith("//Samples/") or (
                len(stripped) > 1 and stripped[1:].startswith("Samples/")
            ):
                merged_lines.append(line + lines[i + 1])
                skip_next = True
                continue

        merged_lines.append(line)

    lines = merged_lines

    # --- Classification ---
    def clean_path(p: str) -> str:
        if not p:
            return None
        if p.startswith("Samples/"):
            return p
        p = p[1:] if len(p) > 1 else ""
        while p.startswith("/"):
            p = p[1:]
        return p if p.startswith("Samples/") else None

    i = 0
    pad_counter = 1
    result = []
    last_cleaned_path = None

    def check_prev_lines(lines, current_index, expansion_name, max_lookback=5):
        for offset in range(1, max_lookback + 1):
            if current_index - offset < 0:
                break
            line = lines[current_index - offset]
            if line == expansion_name:
                return True
            if not is_garbage_line(line):
                break
        return False

    while i < len(lines):
        line = lines[i]
        if line.lower().endswith(".wav"):
            prev_line = lines[i - 1] if i > 0 else ""
            if prev_line != expansion_name:
                multisample = {"type": "multisample", "name": prev_line, "paths": []}
                seen_paths = set()
                i += 1
                cleaned = clean_path(line)
                if cleaned and cleaned != last_cleaned_path and cleaned not in seen_paths:
                    multisample["paths"].append(cleaned)
                    seen_paths.add(cleaned)
                    last_cleaned_path = cleaned
                else:
                    continue

                while i < len(lines):
                    next_line = lines[i]
                    if not next_line.lower().endswith(".wav"):
                        i += 1
                        continue

                    if check_prev_lines(lines, i, expansion_name, max_lookback=4):
                        cleaned = clean_path(next_line)
                        if cleaned and cleaned != last_cleaned_path and cleaned not in seen_paths:
                            multisample["paths"].append(cleaned)
                            seen_paths.add(cleaned)
                            last_cleaned_path = cleaned
                        i += 1
                    else:
                        break

                if len(multisample["paths"]) == 1:
                    multisample["type"] = "sample"
                    multisample["paths"] = multisample["paths"][0]

                multisample["pad"] = pad_counter
                pad_counter += 1  # Always increment — no wraparound
                result.append(multisample)
                continue
        i += 1

    # --- Filter empty multisamples ---
    filtered_result = []
    for entry in result:
        if entry['type'] == "multisample" and not entry['paths']:
            logger.warning(f"Skipped empty multisample in: {group_name}")
            continue
        filtered_result.append(entry)

    # --- Warn if more than 16 pads ---
    if len(filtered_result) > 16:
        logger.warning(f"group '{group_name}' has {len(filtered_result)} pads (more than 16).")

    return filtered_result


def find_mxgrp_files(folder_in: str) -> list[str]:
    """Recursively find all .mxgrp files in folder_in."""
    mxgrp_files = []
    for root, _, files in os.walk(folder_in):
        for file in files:
            if file.lower().endswith(".mxgrp"):
                mxgrp_files.append(os.path.join(root, file))
    return mxgrp_files


def safe_filename(s: str) -> str:
    """
    Make a string safe for filenames:
    - Strip leading/trailing whitespace
    - Replace spaces with underscores
    - Remove characters that are not alnum, underscore, hyphen or dot
    - Collapse repeated underscores
    """
    if not s:
        return "unknown"
    s = s.strip()
    # replace spaces with underscores
    s = s.replace(" ", "_")
    # remove invalid chars
    s = re.sub(r'[^A-Za-z0-9_\-\.]', '', s)
    # collapse multiple underscores
    s = re.sub(r'_+', '_', s)
    return s or "unknown"


def ensure_unique_path(folder: str, filename: str) -> str:
    """
    If filename already exists in folder, append _1, _2, ... until unique.
    Returns the absolute filepath.
    """
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}_{n}{ext}"
        n += 1
    return os.path.join(folder, candidate)


def clear_parsed_folder(output_folder: str):
    parsed_folder = os.path.join(output_folder, "parsed")
    if os.path.exists(parsed_folder):
        # Remove entire folder and recreate it cleanly
        shutil.rmtree(parsed_folder)
    os.makedirs(parsed_folder, exist_ok=True)


def process_mxgrp_file(input_file: str, output_folder: str, generate_txt: bool = True) -> dict:
    with open(input_file, "rb") as f:
        raw_data = try_decompress(f.read())

    strings = extract_clean_strings(raw_data)
    filtered = post_process(strings)

    group_name = os.path.splitext(os.path.basename(input_file))[0]

    abs_input_path = os.path.abspath(input_file)
    folder_two_levels_up = os.path.dirname(os.path.dirname(os.path.dirname(abs_input_path))).replace('\\', '/')

    # Find expansion name
    expansion_name = find_expansion_name(filtered, folder_two_levels_up)

    # Merge expansion names
    if expansion_name in MERGED_EXPANSIONS:
        expansion_name = MERGED_EXPANSIONS[expansion_name]

    # Skip excluded expansions
    if expansion_name in EXCLUDED_EXPANSIONS:
        logger.info(f"Skipped excluded expansion: {expansion_name} (group: {group_name})")
        return None

    sample_data = classify_samples(filtered, group_name, expansion_name)

    # Build safe filename using expansion + group
    safe_exp = safe_filename(expansion_name)
    safe_group = safe_filename(group_name)
    output_filename = f"{safe_exp}_{safe_group}.txt"

    # Ensure parsed subfolder exists
    parsed_folder = os.path.join(output_folder, "parsed")
    os.makedirs(parsed_folder, exist_ok=True)

    # make unique if there's a collision
    output_filepath = ensure_unique_path(parsed_folder, output_filename)

    # write cleaned text file AFTER we know expansion_name
    if generate_txt:
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write('\n'.join(filtered))

    abs_input_path = os.path.abspath(input_file)
    folder_two_levels_up = os.path.dirname(os.path.dirname(os.path.dirname(abs_input_path))).replace('\\', '/')

    group_info = {
        "group": group_name.strip(),
        "expansion": expansion_name,
        "path": folder_two_levels_up,
        "samples": sample_data,
        "txt_file": output_filepath,
    }

    logger.info(f"Processed group: {group_name}, expansion: {expansion_name}, samples: {len(sample_data)}")
    return group_info


def main(folder_in: str, folder_out: str, combined_json_name="all_groups.json", generate_txt=True):
    if not os.path.isdir(folder_out):
        os.makedirs(folder_out)

    # Clear the parsed folder at start
    clear_parsed_folder(folder_out)

    mxgrp_files = find_mxgrp_files(folder_in)
    logger.info(f"Found {len(mxgrp_files)} .mxgrp files to process.")

    all_groups = []

    for mxgrp_path in mxgrp_files:
        try:
            group_data = process_mxgrp_file(mxgrp_path, folder_out, generate_txt=generate_txt)

            if not group_data:  # Skipped due to exclusion
                continue

            # Skip groups with no samples
            if not group_data['samples']:
                logger.warning(f"Skipped group with no samples: {group_data['group']}")
                continue

            all_groups.append(group_data)
        except Exception as e:
            logger.error(f"Error processing '{mxgrp_path}': {e}")

    combined_json_path = os.path.join(folder_out, combined_json_name)
    with open(combined_json_path, "w", encoding="utf-8") as f:
        json.dump(all_groups, f, indent=2, ensure_ascii=False)

    logger.info(f"All groups saved to {combined_json_path}")


class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()


if __name__ == "__main__":

    if len(sys.argv) not in (3, 4):
        logger.error(f"Usage: python {sys.argv[0]} <input_folder> <output_folder> [generate_txt]")
        logger.error("generate_txt: optional, 'true' or 'false' (default: true)")
        sys.exit(1)

    log_path = os.path.join(LOGS_PATH, "_build_groups_log.txt")
    sys.stdout = Tee(sys.stdout, open(log_path, "w", encoding="utf-8"))
    sys.stderr = Tee(sys.stderr, open(log_path, "a", encoding="utf-8"))  # Redirect stderr to the same log file, append mode

    input_folder = sys.argv[1]
    output_folder = sys.argv[2]
    generate_txt = True
    if len(sys.argv) == 4:
        generate_txt = sys.argv[3].lower() == "true"

    main(input_folder, output_folder, generate_txt=generate_txt)
