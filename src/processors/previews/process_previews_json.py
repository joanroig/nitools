import argparse
import json
import os
import sys
from pathlib import Path

from utils.audio_utils import trim_and_normalize_wav
from utils.constants import LOGS_PATH
from utils.logger import Logger

logger = Logger.get_logger("PreviewsProcessor")


def process_previews(
    json_path,
    output_folder,
    trim_silence_flag=False,
    normalize_flag=False,
    sample_rate=None,
    bit_depth=None
):
    with open(json_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    for sample in samples:
        ogg_path = Path(sample["ogg_path"])
        wav_name = sample["wav_name"]
        instrument_folder = sample["instrument"]
        wav_path = Path(output_folder) / instrument_folder / wav_name
        wav_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            trim_and_normalize_wav(
                input_path=str(ogg_path),
                output_path=str(wav_path),
                trim_silence_flag=trim_silence_flag,
                normalize_flag=normalize_flag,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
            )
            logger.info(f"Converted {ogg_path} -> {wav_path}")
        except Exception as e:
            logger.error(f"Failed to convert {ogg_path}: {e}")


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


def main():
    parser = argparse.ArgumentParser(description="preview processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action="store_true", help="Trim silence from wav files")
    parser.add_argument("--normalize", action="store_true", help="Normalize wav files")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")

    args = parser.parse_args()

    process_previews(
        json_path=args.json_path,
        output_folder=args.output_folder,
        trim_silence_flag=args.trim_silence,
        normalize_flag=args.normalize,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )


if __name__ == "__main__":
    log_path = os.path.join(LOGS_PATH, "_process_previews_log.txt")
    sys.stdout = Tee(sys.stdout, open(log_path, "w", encoding="utf-8"))
    sys.stderr = Tee(sys.stderr, open(log_path, "a", encoding="utf-8"))  # Redirect stderr to the same log file, append mode

    main()
