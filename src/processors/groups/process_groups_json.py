import json
import os
import re
import shutil
import sys
import argparse

from utils.audio_utils import trim_and_normalize_wav
from utils.constants import LOGS_PATH
from utils.logger import Logger

logger = Logger.get_logger("GroupsProcessor")

# Default Roland matrix from original pad -> target pad
DEFAULT_MATRIX = {
    1: 13, 2: 14, 3: 15, 4: 16,
    5: 9, 6: 10, 7: 11, 8: 12,
    9: 5, 10: 6, 11: 7, 12: 8,
    13: 1, 14: 2, 15: 3, 16: 4
}

# Default pad filter keywords for filtering groups
DEFAULT_PAD_FILTER = {
    1: ["kick"],
    2: ["snare", "snap", "clap"],
    3: ["hh", "hihat", "hi hat", "shaker"]
}


def pick_multisample_path(paths):
    # Prioritize _C4, _C3
    for p in paths:
        base = os.path.splitext(p)[0].upper()  # case-insensitive
        if base.endswith('_C4'):
            return p
        if base.endswith('_C3'):
            return p

    # Then match _C followed by any single digit
    for p in paths:
        base = os.path.splitext(p)[0].upper()
        if re.search(r'_C\d$', base):
            return p

    # Fallback to the first path
    return paths[0]

def process_group(
    json_path,
    output_folder,
    trim_silence_flag=False,
    matrix=None,
    filter_pads=True,
    pad_filter=None,
    fill_blanks=None,
    normalize_flag=False,
    sample_rate=None,
    bit_depth=None,
    enable_matrix=True,
    include_preview=False
):
    if matrix is None:
        matrix = DEFAULT_MATRIX
    if pad_filter is None:
        pad_filter = DEFAULT_PAD_FILTER

    # Load JSON groups
    with open(json_path, 'r', encoding='utf-8') as f:
        groups = json.load(f)

    def pad_contains(sample, keywords):
        if not sample:
            return False
        name = sample.get('name', '')
        name = name.lower()
        return any(kw in name for kw in keywords)

    filtered_groups = []
    if filter_pads and pad_filter:
        for group in groups:
            samples = group.get('samples', [])
            match = True
            for pad_num, keywords in pad_filter.items():
                pad_sample = next((s for s in samples if s.get('pad') == pad_num), None)
                if not pad_contains(pad_sample, keywords):
                    match = False
                    break
            if match:
                filtered_groups.append(group)
        groups = filtered_groups

    for group in groups:
        group_name = group['group']
        expansion_name = group['expansion']
        base_path = group['path']
        samples = group['samples']

        # Build output group folder path
        group_folder = os.path.join(output_folder, expansion_name, group_name)
        os.makedirs(group_folder, exist_ok=True)

        # For reordering, create a mapping pad -> sample data
        pad_to_sample = {}
        for s in samples:
            pad_to_sample[s['pad']] = s

        # Go through original pads 1..16 (max 16 samples)
        for original_pad in range(1, 17):
            sample = pad_to_sample.get(original_pad)
            target_pad = matrix.get(original_pad, original_pad) if enable_matrix else original_pad
            suffix = f"{target_pad:02d}_"

            if sample:
                # Determine source wav path(s)
                if sample['type'] == 'multisample':
                    # pick one path according to rule
                    source_rel_path = pick_multisample_path(sample['paths'])
                else:
                    source_rel_path = sample['paths']

                source_path = os.path.join(base_path, source_rel_path)
                if not os.path.isfile(source_path):
                    logger.warning(f"Source file not found {source_path}")
                    continue

                filename = os.path.basename(source_path)
                target_filename = suffix + filename
                target_path = os.path.join(group_folder, target_filename)

                try:
                    trim_and_normalize_wav(source_path, target_path, trim_silence_flag, normalize_flag, sample_rate, bit_depth)
                except Exception as e:
                    logger.error(f"Error processing {source_path}: {e}")
                    shutil.copy2(source_path, target_path)

                logger.info(f"Copied pad {original_pad:02d} -> target pad {target_pad:02d} file: {target_path}")
            else:
                # Fill blank pad
                if fill_blanks:
                    import random
                    if os.path.isdir(fill_blanks):
                        # Pick random wav file from folder
                        wavs = [f for f in os.listdir(fill_blanks) if f.lower().endswith('.wav')]
                        if wavs:
                            chosen = random.choice(wavs)
                            source_path = os.path.join(fill_blanks, chosen)
                        else:
                            source_path = None
                    else:
                        source_path = fill_blanks
                    if source_path and os.path.isfile(source_path):
                        target_filename = suffix + os.path.basename(source_path)
                        target_path = os.path.join(group_folder, target_filename)
                        try:
                            trim_and_normalize_wav(source_path, target_path, trim_silence_flag, normalize_flag, sample_rate, bit_depth)
                        except Exception as e:
                            logger.error(f"Error processing {source_path}: {e}")
                            shutil.copy2(source_path, target_path)
                        logger.info(f"Filled blank pad {original_pad:02d} -> target pad {target_pad:02d} with: {target_path}")
                    else:
                        logger.warning(f"No valid file to fill blank pad {original_pad:02d}")
        # Include preview sample if enabled
        if include_preview:
            preview_dir = os.path.join(base_path, "Groups", "groups", ".previews")
            preview_file = os.path.join(preview_dir, group_name + ".mxgrp.ogg")
            if os.path.isfile(preview_file):
                preview_wav = os.path.join(group_folder, "Preview - " + group_name + ".wav")
                try:
                    trim_and_normalize_wav(preview_file, preview_wav, trim_silence_flag, normalize_flag, sample_rate, bit_depth)
                    logger.info(f"Included preview sample: {preview_wav}")
                except Exception as e:
                    logger.error(f"Error processing preview {preview_file}: {e}")


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
    parser = argparse.ArgumentParser(description="group processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action='store_true', help="Trim silence from wav files")
    parser.add_argument("--normalize", action='store_true', help="Normalize wav files")
    parser.add_argument("--matrix_json", help="Optional custom reorder matrix JSON file")
    parser.add_argument("--filter_pads", action='store_true', help="Filter groups: pad 1 contains keywords for pad 1, pad 2 for pad 2, pad 3 for pad 3 (case-insensitive)")
    parser.add_argument("--filter_pads_json", help="Optional custom pad filter keywords JSON file")
    parser.add_argument("--fill_blanks", action='store_true', help="Fill blank pads")
    parser.add_argument("--fill_blanks_path", help="Fill blank pads with file or folder of wavs (default: ./assets/.wav)", default="./assets/.wav")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")
    parser.add_argument("--enable_matrix", action='store_true', help="Enable pad matrix reorder")
    parser.add_argument("--include_preview", action='store_true', help="Include preview samples from groups.previews")

    args = parser.parse_args()

    matrix = None
    if args.matrix_json:
        with open(args.matrix_json, 'r', encoding='utf-8') as f:
            matrix = json.load(f)
            # Expecting a dictionary of str keys (pad numbers) to int values
            # Convert keys to int
            matrix = {int(k): v for k, v in matrix.items()}

    pad_filter = None
    if args.filter_pads_json:
        with open(args.filter_pads_json, 'r', encoding='utf-8') as f:
            pad_filter = json.load(f)
            # Convert keys to int
            pad_filter = {int(k): v for k, v in pad_filter.items()}

    fill_blanks = None
    if args.fill_blanks and args.fill_blanks_path:
        fill_blanks = args.fill_blanks_path
    process_group(
        json_path=args.json_path,
        output_folder=args.output_folder,
        trim_silence_flag=args.trim_silence,
        matrix=matrix,
        filter_pads=args.filter_pads,
        pad_filter=pad_filter,
        fill_blanks=fill_blanks,
        normalize_flag=args.normalize,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
        enable_matrix=args.enable_matrix,
        include_preview=args.include_preview
    )


if __name__ == "__main__":

    log_path = os.path.join(LOGS_PATH, "_process_groups_log.txt")
    sys.stdout = Tee(sys.stdout, open(log_path, "w", encoding="utf-8"))
    sys.stderr = Tee(sys.stderr, open(log_path, "a", encoding="utf-8"))  # Redirect stderr to the same log file, append mode

    main()
