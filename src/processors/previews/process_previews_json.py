import argparse
import json
import sys
from pathlib import Path

from utils.audio_utils import trim_and_normalize_wav
from utils.logger import Logger

logger = Logger.get_logger("PreviewsProcessor")


class PreviewsProcessor:
    def __init__(
        self,
        json_path,
        output_folder,
        trim_silence=False,
        normalize=False,
        sample_rate=None,
        bit_depth=None,
        skip_existing=False
    ):
        self.json_path = json_path
        self.output_folder = output_folder
        self.trim_silence = trim_silence
        self.normalize = normalize
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.skip_existing = skip_existing

    def run(self, worker_instance=None):
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                samples = json.load(f)

            for sample in samples:
                if worker_instance and worker_instance.cancel_requested():
                    logger.info("Previews export cancelled by user.")
                    return 1  # Return non-zero for cancellation

                ogg_path = Path(sample["ogg_path"])
                wav_name = sample["wav_name"]
                instrument_folder = sample["instrument"]
                wav_path = Path(self.output_folder) / instrument_folder / wav_name
                wav_path.parent.mkdir(parents=True, exist_ok=True)

                if self.skip_existing and wav_path.exists():
                    logger.info(f"Skipping existing file: {wav_path}")
                    continue

                try:
                    trim_and_normalize_wav(
                        input_path=str(ogg_path),
                        output_path=str(wav_path),
                        trim_silence=self.trim_silence,
                        normalize=self.normalize,
                        sample_rate=self.sample_rate,
                        bit_depth=self.bit_depth,
                    )
                    logger.info(f"Converted {ogg_path} -> {wav_path}")
                except Exception as e:
                    logger.error(f"Failed to convert {ogg_path}: {e}")
            return 0  # Success
        except Exception as e:
            logger.error(f"Error processing previews: {e}")
            return 1  # Error


def main(json_path: str, output_folder: str, trim_silence: bool, normalize: bool, sample_rate: int, bit_depth: int, skip_existing: bool):
    processor = PreviewsProcessor(
        json_path=json_path,
        output_folder=output_folder,
        trim_silence=trim_silence,
        normalize=normalize,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        skip_existing=skip_existing,
    )
    sys.exit(processor.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="preview processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action="store_true", help="Trim silence from wav files")
    parser.add_argument("--normalize", action="store_true", help="Normalize wav files")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")
    parser.add_argument("--skip_existing", action="store_true", help="Skip processing if output file already exists")

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
            sample_rate=args.sample_rate,
            bit_depth=args.bit_depth,
            skip_existing=args.skip_existing,
        )
    except SystemExit as e:
        sys.exit(e.code)
