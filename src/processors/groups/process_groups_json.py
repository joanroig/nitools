import argparse
import json
import sys
from pathlib import Path

from models.matrix_config import MatrixConfig
from models.pad_filter_config import PadFilterConfig
from processors.sample_export import SampleCollectionProcessor
from processors.instrument_render import RenderOptions
from utils.logger import Logger

logger = Logger.get_logger("GroupsProcessor")


class GroupsProcessor(SampleCollectionProcessor):
    def __init__(
        self, json_path, output_folder, trim_silence=False, matrix=None,
        filter_pads=False, pad_filter=None, fill_blanks=None, normalize=False,
        sample_rate=None, bit_depth=None, enable_matrix=True,
        include_preview=False, skip_existing=False,
        render_options=None,
    ):
        self.render_options = RenderOptions.model_validate(render_options or {})
        super().__init__(
            json_path, output_folder, kind="group", logger=logger,
            trim_silence=trim_silence, normalize=normalize,
            sample_rate=sample_rate, bit_depth=bit_depth, matrix=matrix,
            enable_matrix=enable_matrix, filter_pads=filter_pads,
            pad_filter=pad_filter, include_preview=include_preview,
            skip_existing=skip_existing, fill_blanks=fill_blanks,
        )


def main(
    json_path: str,
    output_folder: str,
    trim_silence: bool,
    normalize: bool,
    matrix_json: str,
    filter_pads: bool,
    filter_pads_json: str,
    fill_blanks: bool,
    fill_blanks_path: str,
    sample_rate: int,
    bit_depth: int,
    enable_matrix: bool,
    include_preview: bool,
    skip_existing: bool,
    render_instruments=False, vst2_folder='', render_note=60,
    render_velocity=100, render_hold=1.0, render_tail=2.0,
    render_maschine=False, maschine_plugin='', maschine_cache='',
    auto_prepare=True, prepare_timeout=120,
):
    # Matrix
    if matrix_json:
        with open(matrix_json, 'r', encoding='utf-8') as f:
            loaded_dict = {int(k): v for k, v in json.load(f).items()}
            matrix = MatrixConfig(pads=loaded_dict)
    else:
        matrix = MatrixConfig()

    # Pad filter
    if filter_pads_json:
        with open(filter_pads_json, 'r', encoding='utf-8') as f:
            loaded_dict = {int(k): v for k, v in json.load(f).items()}
            pad_filter = PadFilterConfig(pads=loaded_dict)
    else:
        pad_filter = PadFilterConfig()

    actual_fill_blanks_path = None
    if fill_blanks and fill_blanks_path:
        actual_fill_blanks_path = fill_blanks_path

    processor = GroupsProcessor(
        json_path=json_path,
        output_folder=output_folder,
        trim_silence=trim_silence,
        matrix=matrix,
        filter_pads=filter_pads,
        pad_filter=pad_filter,
        fill_blanks=actual_fill_blanks_path,
        normalize=normalize,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        enable_matrix=enable_matrix,
        include_preview=include_preview,
        skip_existing=skip_existing,
        render_options=dict(enabled=render_instruments, plugin_folder=vst2_folder,
                            native_enabled=render_maschine, maschine_plugin=maschine_plugin, cache_folder=maschine_cache,
                            auto_prepare=auto_prepare, prepare_timeout=prepare_timeout,
                            note=render_note, velocity=render_velocity,
                            hold=render_hold, tail=render_tail),
    )
    sys.exit(processor.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="group processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action='store_true', help="Trim silence from wav files")
    parser.add_argument("--normalize", action='store_true', help="Normalize wav files")
    parser.add_argument("--matrix_json", help="Optional custom reorder matrix JSON file")
    parser.add_argument("--filter_pads", action='store_true', help="Filter groups: pad 1 contains keywords for pad 1, pad 2 for pad 2, pad 3 for pad 3 (case-insensitive)")
    parser.add_argument("--filter_pads_json", help="Optional custom pad filter keywords JSON file")
    parser.add_argument("--fill_blanks", action='store_true', help="Fill blank pads")
    parser.add_argument("--fill_blanks_path", help="Fill blank pads with file or folder of wavs (default: resources/audio/.wav)", default="resources/audio/.wav")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")
    parser.add_argument("--enable_matrix", action='store_true', help="Enable pad matrix reorder")
    parser.add_argument("--include_preview", action='store_true', help="Include preview samples from groups.previews")
    parser.add_argument("--skip_existing", action='store_true', help="Skip processing if output file already exists")
    parser.add_argument('--render_instruments', action='store_true', help='Render supported external VST2 instruments (Windows, experimental)')
    parser.add_argument('--vst2_folder', default='', help='Additional folder containing installed 64-bit VST2 DLLs')
    parser.add_argument('--render_maschine', action='store_true', help='Render instruments through prepared Maschine 3 kit states (Windows, experimental)')
    parser.add_argument('--maschine_plugin', default='', help='Installed Maschine 3.vst3 path; detected automatically by default')
    parser.add_argument('--maschine_cache', default='', help='Prepared kit cache folder; defaults to the NITools user cache')
    parser.add_argument('--no_auto_prepare', action='store_true', help='Only use previously prepared Maschine kits')
    parser.add_argument('--prepare_timeout', type=float, default=120, help='Maximum automatic kit loading time in seconds')
    parser.add_argument('--render_note', type=int, default=60, help='MIDI note number, 0–127 (default: 60)')
    parser.add_argument('--render_velocity', type=int, default=100)
    parser.add_argument('--render_hold', type=float, default=1.0, help='Note duration in seconds')
    parser.add_argument('--render_tail', type=float, default=2.0, help='Release duration in seconds')

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

    if args.matrix_json and not Path(args.matrix_json).is_file():
        logger.error(f"Error: Matrix JSON path '{args.matrix_json}' does not exist or is not a file.")
        sys.exit(1)

    if args.filter_pads_json and not Path(args.filter_pads_json).is_file():
        logger.error(f"Error: Pad filter JSON path '{args.filter_pads_json}' does not exist or is not a file.")
        sys.exit(1)

    if args.fill_blanks and args.fill_blanks_path:
        fill_path = Path(args.fill_blanks_path)
        if not fill_path.exists():
            logger.error(f"Error: Fill blanks path '{args.fill_blanks_path}' does not exist.")
            sys.exit(1)
        if not (fill_path.is_file() or fill_path.is_dir()):
            logger.error(f"Error: Fill blanks path '{args.fill_blanks_path}' is not a file or a directory.")
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
            matrix_json=args.matrix_json,
            filter_pads=args.filter_pads,
            filter_pads_json=args.filter_pads_json,
            fill_blanks=args.fill_blanks,
            fill_blanks_path=args.fill_blanks_path,
            sample_rate=args.sample_rate,
            bit_depth=args.bit_depth,
            enable_matrix=args.enable_matrix,
            include_preview=args.include_preview,
            skip_existing=args.skip_existing,
            render_instruments=args.render_instruments, vst2_folder=args.vst2_folder,
            render_note=args.render_note, render_velocity=args.render_velocity,
            render_hold=args.render_hold, render_tail=args.render_tail,
            render_maschine=args.render_maschine, maschine_plugin=args.maschine_plugin, maschine_cache=args.maschine_cache,
            auto_prepare=not args.no_auto_prepare, prepare_timeout=args.prepare_timeout,
        )
    except SystemExit as e:
        sys.exit(e.code)
