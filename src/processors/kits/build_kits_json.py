import argparse
from pathlib import Path

from formats.battery import parse_battery
from processors.index_utils import find_sources, build_sample_index
from utils.file_utils import ensure_unique_path, sanitize
from utils.logger import Logger

logger = Logger.get_logger("KitsBuilder")


def find_nbkt_files(folder_in: str, worker_instance=None) -> list[str]:
    return find_sources(folder_in, '.nbkt', worker_instance)


def process_nbkt_file(input_file: str, output_folder: str, generate_txt: bool = True, decoded=None) -> dict:
    source = Path(input_file).resolve()
    kit = parse_battery(source.read_bytes()) if decoded is None else decoded
    library = next((parent for parent in source.parents if (parent / "Samples").is_dir()), None)
    preview = source.parent / ".previews" / (source.name + ".ogg")
    kit.update({
        "source": "Battery", "path": source.as_posix(),
        "sample_root": source.parent.as_posix(),
        "expansion": library.name if library else source.parent.name,
        "preview": preview.as_posix() if preview.is_file() else None,
        "txt_file": None,
    })
    if generate_txt:
        parsed = Path(output_folder) / "parsed"
        parsed.mkdir(parents=True, exist_ok=True)
        target = Path(ensure_unique_path(str(parsed), sanitize(kit["expansion"] + "_" + source.stem) + ".txt"))
        target.write_text("\n".join(
            f"{sample['pad']:02d}\t{path}"
            for sample in kit["samples"] for path in sample["paths"]
        ) + "\n", encoding="utf-8")
        kit["txt_file"] = str(target)
    if kit.get("hidden_cells"):
        logger.warning("%s has %s populated cells outside its saved grid; retained in the index, not assigned export pads.",
                       kit["kit"], len(kit["hidden_cells"]))
    logger.info("Decoded kit: %s (%s x %s, %s sample zones)", kit["kit"], kit["rows"], kit["columns"], kit["zone_count"])
    return kit


class KitsJsonBuilder:
    def __init__(self, input_folder: str, output_folder: str,
                 combined_json_name: str = "all_kits.json", generate_txt: bool = True):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.combined_json_name = combined_json_name
        self.generate_txt = generate_txt

    def run(self, worker_instance=None):
        try:
            if not Path(self.input_folder).is_dir():
                raise ValueError(f"Input folder does not exist: {self.input_folder}")
            output = Path(self.output_folder)
            output.mkdir(parents=True, exist_ok=True)
            logger.info("Scanning for Battery kits in %s", self.input_folder)
            sources = find_nbkt_files(self.input_folder, worker_instance)
            logger.info("Found %s .nbkt files to decode.", len(sources))
            return build_sample_index(
                sources, Path(self.output_folder) / self.combined_json_name,
                parse_battery, process_nbkt_file, generate_txt=self.generate_txt,
                worker=worker_instance, logger=logger, label="kits")
        except Exception as exc:
            logger.error("Error building kits JSON: %s", exc)
            return 1


def main(input_folder: str, output_folder: str,
         combined_json_name: str = "all_kits.json", generate_txt: bool = True):
    return KitsJsonBuilder(input_folder, output_folder, combined_json_name, generate_txt).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decode Native Instruments Battery kit sample references.")
    parser.add_argument("input_folder")
    parser.add_argument("output_folder")
    parser.add_argument("--combined_json_name", default="all_kits.json")
    parser.add_argument("--generate_txt", type=lambda value: value.lower() == "true", default=True)
    args = parser.parse_args()
    raise SystemExit(main(args.input_folder, args.output_folder, args.combined_json_name, args.generate_txt))
