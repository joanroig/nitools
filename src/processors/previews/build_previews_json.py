import argparse
import json
import platform  # Added import
import sys
from pathlib import Path

# Conditional import for winreg
if platform.system() == "Windows":
    import winreg

from utils.constants import LOGS_PATH
from utils.logger import Logger

logger = Logger.get_logger("PreviewsBuilder")

# Registry path to Native Instruments registry (Windows only)
REG_PATH = r"SOFTWARE\Native Instruments"


def get_windows_content_paths():
    """Return all ContentDir values for Native Instruments products from the Windows registry."""
    content_paths = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH) as ni_key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(ni_key, i)
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{REG_PATH}\\{subkey_name}") as inst_key:
                            value, _ = winreg.QueryValueEx(inst_key, "ContentDir")
                            path = Path(value)
                            if path.exists() and path.is_dir():
                                content_paths.append((subkey_name, path))  # Store (instrument_name, path)
                    except FileNotFoundError:
                        logger.debug(f"ContentDir for {subkey_name} not found in registry.")
                    except OSError as e:
                        logger.warning(f"Error accessing registry for {subkey_name}: {e}")
                    i += 1
                except OSError:  # No more subkeys
                    break
    except FileNotFoundError:
        logger.warning(f"Windows Registry path {REG_PATH} not found.")
    return content_paths


def get_macos_content_paths():
    """Return common Native Instruments content directories on macOS."""
    base_search_paths = [
        Path("/Users/Shared/Native Instruments"),
        Path.home() / "Library/Application Support/Native Instruments",
        Path("/Library/Application Support/Native Instruments"),
    ]
    found_content_dirs = set()

    for base_path in base_search_paths:
        if base_path.exists() and base_path.is_dir():
            # Search for .nicnt files (Kontakt libraries) or .previews folders
            for nicnt_file in base_path.rglob("*.nicnt"):
                content_dir = nicnt_file.parent
                if content_dir.is_dir():
                    found_content_dirs.add(content_dir)

            for previews_folder in base_path.rglob(".previews"):
                current_path = previews_folder
                # Traverse up to find the library root
                while current_path != base_path and current_path.parent != current_path:
                    # If the parent is one of the base search paths, then current_path is a library root
                    if current_path.parent in base_search_paths:
                        found_content_dirs.add(current_path)
                        break
                    # If current_path itself contains a .nicnt, it's a library root
                    if list(current_path.glob("*.nicnt")):
                        found_content_dirs.add(current_path)
                        break
                    current_path = current_path.parent
                else:  # If loop completes without break, add the highest level found before hitting base_path or root
                    if current_path != base_path:
                        found_content_dirs.add(current_path)

    # Convert set of paths to list of (instrument_name, path) tuples
    result = []
    for path in found_content_dirs:
        # Use the folder name as the instrument name
        instrument_name = path.name
        result.append((instrument_name, path))
    return result


def get_ni_content_paths():
    """Returns a list of (instrument_name, Path_object) tuples for NI content directories,
    platform-agnostic."""
    if platform.system() == "Windows":
        return get_windows_content_paths()
    elif platform.system() == "Darwin":  # macOS
        return get_macos_content_paths()
    else:
        logger.warning(f"Unsupported operating system: {platform.system()}. Cannot find NI content paths.")
        return []


def collect_samples_from_path(instrument_name: str, content_dir: Path):
    """Collect all .ogg files and their corresponding output paths from a given content directory."""
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
                    "instrument": instrument_name,
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

            # Get content paths based on OS
            ni_content_paths = get_ni_content_paths()

            for inst_name, content_dir_path in ni_content_paths:
                if worker_instance and worker_instance.cancel_requested():
                    logger.info("Previews JSON build cancelled by user.")
                    return 1  # Return non-zero for cancellation

                logger.info(f"Collecting samples for: {inst_name} from {content_dir_path}")
                all_samples.extend(collect_samples_from_path(inst_name, content_dir_path))

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
