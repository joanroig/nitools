import argparse
import json
import os
import re
import shutil
import sys
import zlib
from pathlib import Path

from utils.file_utils import ensure_unique_path, sanitize
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


def clear_parsed_folder(output_folder: str):
    parsed_folder = os.path.join(output_folder, "parsed")
    if os.path.exists(parsed_folder):
        # Remove entire folder and recreate it cleanly
        shutil.rmtree(parsed_folder)
    os.makedirs(parsed_folder, exist_ok=True)

def find_group_path(path):
    path = os.path.abspath(path)
    while not os.path.isdir(os.path.join(path, "Samples")):
        parent = os.path.dirname(path)
        if parent == path:
            raise FileNotFoundError("No 'Samples' folder found.")
        path = parent
    return path.replace('\\', '/')

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
    safe_exp = sanitize(expansion_name)
    safe_group = sanitize(group_name)
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

    group_path = find_group_path(input_file)

    group_info = {
        "group": group_name.strip(),
        "expansion": expansion_name,
        "path": group_path,
        "samples": sample_data,
        "txt_file": output_filepath,
    }

    logger.info(f"Processed group: {group_name}, expansion: {expansion_name}, samples: {len(sample_data)}")
    return group_info


class GroupsJsonBuilder:
    def __init__(self, input_folder: str, output_folder: str, combined_json_name="all_groups.json", generate_txt=True):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.combined_json_name = combined_json_name
        self.generate_txt = generate_txt

    def run(self, worker_instance=None):  # Accept worker_instance
        try:
            if not os.path.isdir(self.output_folder):
                os.makedirs(self.output_folder)

            clear_parsed_folder(self.output_folder)

            mxgrp_files = find_mxgrp_files(self.input_folder)
            logger.info(f"Found {len(mxgrp_files)} .mxgrp files to process.")

            all_groups = []

            for mxgrp_path in mxgrp_files:
                if worker_instance and worker_instance.cancel_requested():  # Check for cancellation
                    logger.info("Groups JSON build cancelled by user.")
                    return 1  # Return non-zero for cancellation

                try:
                    group_data = process_mxgrp_file(mxgrp_path, self.output_folder, generate_txt=self.generate_txt)

                    if not group_data:
                        continue

                    if not group_data['samples']:
                        logger.warning(f"Skipped group with no samples: {group_data['group']}")
                        continue

                    all_groups.append(group_data)
                except Exception as e:
                    logger.error(f"Error processing '{mxgrp_path}': {e}")

            combined_json_path = os.path.join(self.output_folder, self.combined_json_name)
            with open(combined_json_path, "w", encoding="utf-8") as f:
                json.dump(all_groups, f, indent=2, ensure_ascii=False)

            logger.info(f"All groups saved to {combined_json_path}")
            return 0
        except Exception as e:
            logger.error(f"Error building groups JSON: {e}")
            return 1

def main(input_folder: str, output_folder: str, combined_json_name: str = "all_groups.json", generate_txt: bool = True):
    builder = GroupsJsonBuilder(
        input_folder=input_folder,
        output_folder=output_folder,
        combined_json_name=combined_json_name,
        generate_txt=generate_txt
    )
    sys.exit(builder.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Builds a JSON file of Native Instruments groups.")
    parser.add_argument("input_folder", help="Path to the input folder containing .mxgrp files.")
    parser.add_argument("output_folder", help="Path to the output folder for the JSON and parsed text files.")
    parser.add_argument("--combined_json_name", default="all_groups.json",
                        help="Name of the combined JSON file (default: all_groups.json).")
    parser.add_argument("--generate_txt", type=lambda x: x.lower() == 'true', default=True,
                        help="Generate individual parsed text files for each group (default: true).")
    args = parser.parse_args()

    # Parameter Validation
    if not os.path.isdir(args.input_folder):
        logger.error(f"Error: Input folder '{args.input_folder}' does not exist or is not a directory.")
        sys.exit(1)

    output_dir = Path(args.output_folder)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error: Could not create output folder '{args.output_folder}': {e}")
        sys.exit(1)

    try:
        main(
            input_folder=args.input_folder,
            output_folder=args.output_folder,
            combined_json_name=args.combined_json_name,
            generate_txt=args.generate_txt
        )
    except SystemExit as e:
        sys.exit(e.code)
