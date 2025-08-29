import argparse
import json
import sys
import winreg
from pathlib import Path

from utils.constants import LOGS_PATH
from utils.logger import Logger

logger = Logger.get_logger("PreviewsBuilder")

# Registry path to Native Instruments registry
REG_PATH = r"SOFTWARE\Native Instruments"


def get_registry_keys(base_key, path):
    """Return all subkeys in a given registry path."""
    keys = []
    try:
        with winreg.OpenKey(base_key, path) as reg_key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(reg_key, i)
                    keys.append(subkey_name)
                    i += 1
                except OSError:
                    break
    except FileNotFoundError:
        logger.warning(f"Registry path {path} not found.")
    return keys


def get_content_dir(inst_name):
    """Return the ContentDir value for a given instrument from the registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{REG_PATH}\\{inst_name}") as key:
            value, _ = winreg.QueryValueEx(key, "ContentDir")
            return Path(value)
    except FileNotFoundError:
        logger.warning(f"ContentDir for {inst_name} not found.")
        return None


def collect_samples(inst_name):
    """Collect all .ogg files and their corresponding output paths."""
    content_dir = get_content_dir(inst_name)
    if not content_dir or not content_dir.exists():
        return []

    samples = []
    for folder in content_dir.rglob(".previews"):
        if folder.is_dir():
            for ogg_file in folder.glob("*.ogg"):
                # Remove specific extensions from the filename if present
                filename = ogg_file.stem
                extensions_to_strip = {".nkm", ".nabs", ".nkl", ".mxinst", ".nkt", ".nrkt", ".nbkt", ".nksf", ".nksn", ".nki", ".nkbt", ".nfm8", ".mxsnd", ".nmsv", ".mxgrp", ".nksr"}

                for ext in extensions_to_strip:
                    if filename.lower().endswith(ext):
                        filename = filename[: -len(ext)]
                        break  # Stop after removing the first matching extension

                samples.append({
                    "instrument": inst_name,
                    "ogg_path": str(ogg_file),
                    "wav_name": f"{filename}.wav",
                })
    return samples


class PreviewsJsonBuilder:
    def __init__(self, output_folder: str):
        self.output_folder = output_folder

    def run(self, worker_instance=None):
        try:
            output_path = Path(self.output_folder)
            output_path.mkdir(exist_ok=True)

            all_samples = []
            instrument_keys = get_registry_keys(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
            for inst in instrument_keys:
                if worker_instance and worker_instance.cancel_requested():
                    logger.info("Previews JSON build cancelled by user.")
                    return 1  # Return non-zero for cancellation

                logger.info(f"Collecting samples for: {inst}")
                all_samples.extend(collect_samples(inst))

            # Save to JSON
            output_json_path = output_path / "all_previews.json"
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(all_samples, f, indent=4)

            logger.info(f"Exported {len(all_samples)} samples to {output_json_path}")
            return 0  # Success
        except Exception as e:
            logger.error(f"Error building previews JSON: {e}")
            return 1  # Error


def main(output_folder: str):
    builder = PreviewsJsonBuilder(output_folder=output_folder)
    sys.exit(builder.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Builds a JSON file of Native Instruments previews.")
    parser.add_argument("output_folder", help="Path to the output folder where the JSON will be saved.")
    args = parser.parse_args()

    # Parameter Validation
    output_dir = Path(args.output_folder)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error: Could not create output folder '{args.output_folder}': {e}")
        sys.exit(1)

    try:
        main(output_folder=args.output_folder)
    except SystemExit as e:
        sys.exit(e.code)
