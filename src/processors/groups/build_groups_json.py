import argparse
import json
import os
import sys
from pathlib import Path

from formats.maschine import parse_maschine
from processors.index_utils import find_sources, report_progress
from processors.groups.parallel_decode import decoded_groups
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

def find_mxgrp_files(folder_in: str, worker_instance=None) -> list[str]:
    """Recursively find all .mxgrp files in folder_in."""
    return find_sources(folder_in, '.mxgrp', worker_instance)


def find_group_path(path):
    path = os.path.abspath(path)
    while not os.path.isdir(os.path.join(path, "Samples")):
        parent = os.path.dirname(path)
        if parent == path:
            raise FileNotFoundError("No 'Samples' folder found.")
        path = parent
    return path.replace('\\', '/')

def process_mxgrp_file(input_file: str, output_folder: str, generate_txt: bool = True, decoded=None) -> dict:
    if decoded is None:
        decoded = parse_maschine(Path(input_file).read_bytes())
    group_name = decoded["group"]
    expansion_name = decoded["expansion"]
    abs_input_path = os.path.abspath(input_file)

    # Merge expansion names
    if expansion_name in MERGED_EXPANSIONS:
        expansion_name = MERGED_EXPANSIONS[expansion_name]

    # Skip excluded expansions
    if expansion_name in EXCLUDED_EXPANSIONS:
        logger.info(f"Skipped excluded expansion: {expansion_name} (group: {group_name})")
        return None

    sample_data = decoded["samples"]

    # Diagnostics contain decoded fields and their source offsets.
    output_filepath = None
    if generate_txt:
        parsed_folder = os.path.join(output_folder, "parsed")
        os.makedirs(parsed_folder, exist_ok=True)
        output_filename = f"{sanitize(expansion_name)}_{sanitize(group_name)}.txt"
        output_filepath = ensure_unique_path(parsed_folder, output_filename)
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(decoded, f, indent=2, ensure_ascii=False)

    try:
        group_path = find_group_path(input_file)
    except FileNotFoundError:
        # MIDI/external-instrument groups can contain no sample references.
        # Absolute references also do not need a sibling Samples directory.
        group_path = str(Path(input_file).resolve().parent)

    # The preview sits in a .previews folder next to the .mxgrp, whatever depth the library nests its groups at
    preview = os.path.join(os.path.dirname(abs_input_path), ".previews", os.path.basename(input_file) + ".ogg")
    preview_rel = os.path.relpath(preview, group_path).replace("\\", "/") if os.path.isfile(preview) else None

    group_info = {
        "group": group_name.strip(),
        "expansion": expansion_name,
        "path": group_path,
        "preview": preview_rel,
        "samples": sample_data,
        "txt_file": output_filepath if generate_txt else None,
        "source_file": abs_input_path,
        "sample_root": group_path,
        "parser": "structured-v1",
        "source": "Maschine",
        "format_details": decoded["format_details"],
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
            if not os.path.isdir(self.input_folder):
                raise ValueError(f"Input folder does not exist: {self.input_folder}")
            if not os.path.isdir(self.output_folder):
                os.makedirs(self.output_folder)

            logger.info("Scanning for Maschine groups in %s", self.input_folder)
            mxgrp_files = find_mxgrp_files(self.input_folder, worker_instance)
            logger.info(f"Found {len(mxgrp_files)} .mxgrp files to process.")

            all_groups = []
            errors = []

            report_progress(worker_instance, 0, len(mxgrp_files), f"0/{len(mxgrp_files)} groups processed\nStarting decoder…")
            with decoded_groups(mxgrp_files, worker_instance) as decoded_files:
                for number, (mxgrp_path, decoded, error) in enumerate(decoded_files, 1):
                    if worker_instance and worker_instance.cancel_requested():
                        logger.info("Groups JSON build cancelled by user.")
                        return 1

                    try:
                        report_progress(worker_instance, number - 1, len(mxgrp_files), f"{number - 1}/{len(mxgrp_files)} groups processed — {Path(mxgrp_path).stem}\n{len(all_groups)} decoded · {len(errors)} errors")
                        if error is not None:
                            raise ValueError(error)
                        group_data = process_mxgrp_file(mxgrp_path, self.output_folder, generate_txt=self.generate_txt, decoded=decoded)
                        if group_data:
                            all_groups.append(group_data)
                    except Exception as e:
                        logger.error(f"Error processing '{mxgrp_path}': {e}")
                        errors.append({"path": mxgrp_path, "error": str(e)})
                    report_progress(worker_instance, number, len(mxgrp_files), f"{number}/{len(mxgrp_files)} groups processed\n{len(all_groups)} decoded · {len(errors)} errors")

            if worker_instance and worker_instance.cancel_requested():
                logger.info("Groups JSON build cancelled by user.")
                return 1
            combined_json_path = os.path.join(self.output_folder, self.combined_json_name)
            with open(combined_json_path, "w", encoding="utf-8") as f:
                json.dump(all_groups, f, indent=2, ensure_ascii=False)

            report_path = Path(combined_json_path).with_suffix(".report.json")
            report_path.write_text(json.dumps({
                "parser": "structured-v1", "files": len(mxgrp_files),
                "decoded": len(all_groups), "errors": errors,
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            log = logger.error if errors or not mxgrp_files else logger.info
            log("Group index %s: %s decoded, %s errors. Saved to %s; details: %s",
                "incomplete" if errors or not mxgrp_files else "complete", len(all_groups), len(errors), combined_json_path, report_path)
            return 1 if errors or not mxgrp_files else 0
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
    from multiprocessing import freeze_support
    freeze_support()
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
