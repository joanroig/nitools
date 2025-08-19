import json
import os
import sys
import winreg
from pathlib import Path

# Registry path to Native Instruments software
REG_PATH = r"SOFTWARE\Native Instruments"

# Output JSON file will be created in the output folder
# OUTPUT_JSON = Path("samples.json")

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
        print(f"Registry path {path} not found.")
    return keys

def get_content_dir(inst_name):
    """Return the ContentDir value for a given instrument from the registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{REG_PATH}\\{inst_name}") as key:
            value, _ = winreg.QueryValueEx(key, "ContentDir")
            return Path(value)
    except FileNotFoundError:
        print(f"ContentDir for {inst_name} not found.")
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

def main(output_folder: str):
    output_path = Path(output_folder)
    output_path.mkdir(exist_ok=True)

    all_samples = []
    instrument_keys = get_registry_keys(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    for inst in instrument_keys:
        print(f"Collecting samples for: {inst}")
        all_samples.extend(collect_samples(inst))

    # Save to JSON
    output_json_path = output_path / "previews.json"
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, indent=4)

    print(f"Exported {len(all_samples)} samples to {output_json_path}")


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
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <output_folder>")
        sys.exit(1)

    output_folder = sys.argv[1]

    # --- Add this before running main ---
    log_dir = output_folder
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "_build_previews_log.txt")
    sys.stdout = Tee(sys.stdout, open(log_path, "w", encoding="utf-8"))

    main(output_folder)
