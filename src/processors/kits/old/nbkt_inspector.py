#!/usr/bin/env python3
"""
nbkt_inspector.py
Heuristic inspector for Native Instruments .nbkt (Battery kit) files.

Usage:
    python nbkt_inspector.py /path/to/kit.nbkt

What it does:
 - prints a small hex header preview
 - extracts ASCII and UTF-16LE printable strings
 - finds candidate audio/sample file paths (wav, aif, ncw, etc)
 - scans for 4-byte ASCII tag + 4-byte uint32 length patterns (chunk-like)
 - writes a JSON summary next to the inspected file

Limitations:
 - This is exploratory tooling, not a full format parser (no official spec).
 - Works best when run on real .nbkt files; use outputs to refine parsing rules.
"""

import json
import os
import re
import struct
import sys
from collections import Counter

# --- helpers ---
PRINTABLE = set(bytes(range(32, 127)).decode('latin1'))  # basic printable ASCII

def hexdump(b: bytes, length=64):
    # return a compact hex preview
    sample = b[:length]
    return ' '.join(f'{c:02x}' for c in sample)

def extract_ascii_strings(b: bytes, min_len=4):
    # classic ASCII string extractor
    reg = re.compile(rb'[\x20-\x7E]{%d,}' % min_len)
    return [m.decode('latin1') for m in reg.findall(b)]

def extract_utf16le_strings(b: bytes, min_len=4):
    # find UTF-16LE encoded printable sequences (simple heuristic)
    # pattern: (printable byte + \x00) repeated
    reg = re.compile(rb'(?:[\x20-\x7E]\x00){%d,}' % min_len)
    raw_matches = reg.findall(b)
    out = []
    for rm in raw_matches:
        try:
            s = rm.decode('utf-16le')
            out.append(s)
        except Exception:
            continue
    return out

def find_paths(strings):
    # heuristic: strings that look like file paths or have audio extensions
    path_like = []
    audio_exts = ('.wav', '.aif', '.aiff', '.flac', '.ncw', '.mp3', '.ogg', '.sfz')
    for s in strings:
        lower = s.lower()
        if any(ext in lower for ext in audio_exts) or '/' in s or '\\' in s:
            # filter out overly short or nonsense entries
            if len(s) >= 6:
                path_like.append(s)
    return path_like

def scan_for_chunks(b: bytes, window=0x1000000):
    """
    Scan binary for sequences that look like:
      4 ASCII letters (A-Z,a-z,0-9, punctuation) followed by a uint32 (little-endian) length,
    and ensure the length is sane for the file (offset + length <= file size).
    Return candidate list of (offset, tag, length).
    """
    candidates = []
    n = len(b)
    for off in range(0, n - 8):
        header = b[off:off + 4]
        # ASCII tag heuristic: printable characters (letters/digits/_-)
        if all(32 <= c < 127 for c in header):
            tag = header.decode('latin1')
            # read next 4 bytes as uint32 little-endian
            length_bytes = b[off + 4:off + 8]
            length = struct.unpack('<I', length_bytes)[0]
            # sanity check the length
            if 0 < length <= n and (off + 8 + length) <= n:
                # filter unrealistic very large lengths (relative)
                if length < window:
                    candidates.append({'offset': off, 'tag': tag, 'length': length})
    # deduplicate by (tag,length) reporting earliest offsets
    seen = {}
    out = []
    for c in candidates:
        key = (c['tag'], c['length'])
        if key not in seen or c['offset'] < seen[key]:
            seen[key] = c['offset']
    for (tag, length), off in seen.items():
        out.append({'tag': tag, 'length': length, 'offset': off})
    # sort by offset
    out.sort(key=lambda x: x['offset'])
    return out

def find_magic(b: bytes):
    # look for known magic signatures: PK (zip), RIF(F) variants, "NI" patterns, NCW etc.
    sigs = {
        'PKZIP': b'PK\x03\x04',
        'RIFF': b'RIFF',
        'NCW': b'NCW',      # just in case NCW names appear
        'NKI': b'NKI',
        'NKX': b'NKX',
        'NBKT_INDICATOR': b'NBKT'  # heuristic
    }
    found = {}
    for name, sig in sigs.items():
        pos = b.find(sig)
        if pos != -1:
            found[name] = pos
    return found

# --- main inspector ---
def inspect_file(path):
    with open(path, 'rb') as f:
        data = f.read()

    report = {}
    report['file'] = os.path.abspath(path)
    report['size'] = len(data)
    report['header_hex'] = hexdump(data, length=128)
    report['magics'] = find_magic(data)

    ascii_strings = extract_ascii_strings(data, min_len=4)
    utf16_strings = extract_utf16le_strings(data, min_len=4)

    # frequency counts of short strings (helpful to spot repeated tags)
    ascii_counter = Counter(s for s in ascii_strings if len(s) <= 64)  # only smaller ones
    top_ascii = ascii_counter.most_common(200)

    report['ascii_strings_sample'] = ascii_strings[:200]   # sample first 200
    report['utf16_strings_sample'] = utf16_strings[:200]
    report['top_ascii_counts'] = top_ascii

    # candidate file paths / sample mentions
    report['candidate_paths'] = find_paths(ascii_strings + utf16_strings)

    # chunk-like scan
    report['chunk_candidates'] = scan_for_chunks(data)

    # try to detect embedded zip (PK) offsets and list next bytes
    pk_off = data.find(b'PK\x03\x04')
    if pk_off != -1:
        report['embedded_zip_offset'] = pk_off
        report['embedded_zip_preview_hex'] = hexdump(data[pk_off:pk_off + 64])

    return report

def main():
    if len(sys.argv) != 2:
        print("Usage: python nbkt_inspector.py /path/to/file.nbkt")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print("File not found:", path)
        sys.exit(1)

    print(f"Inspecting: {path}")
    report = inspect_file(path)
    # pretty print a short human summary
    print("\n=== Summary ===")
    print("File size:", report['size'])
    print("Header (first bytes):", report['header_hex'][:200])
    print("Detected magics:", report['magics'])
    print("Number of ASCII candidate strings found (sampleed):", len(report['ascii_strings_sample']))
    print("Number of UTF-16LE candidate strings (sample):", len(report['utf16_strings_sample']))
    print("Number of candidate chunk patterns:", len(report['chunk_candidates']))
    print("Candidate paths (first 30):")
    for p in report['candidate_paths'][:30]:
        print("  ", p)
    print("\nChunk candidates (first 20):")
    for c in report['chunk_candidates'][:20]:
        print("  offset=0x{offset:x} tag='{tag}' length={length}".format(**c))

    # write JSON report next to the file
    json_path = path + '.inspect.json'
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(report, jf, indent=2, ensure_ascii=False)
    print(f"\nWrote JSON report: {json_path}")


if __name__ == '__main__':
    main()
