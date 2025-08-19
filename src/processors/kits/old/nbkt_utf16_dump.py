#!/usr/bin/env python3
"""
nbkt_bruteforce.py

Aggressive extractor for .nbkt (or any binary) to try many decodings / decompressions / transforms.
Writes results to ./out by default.

Usage:
    python nbkt_bruteforce.py /path/to/file.nbkt [outdir]

Notes:
 - May create many files. Use on a local copy.
 - Safe decompression attempts only; proprietary formats (NCW) won't be decoded here.
"""
import sys
import os
import re
import struct
import zlib
import gzip
import lzma
import bz2
from collections import Counter

def ensure_dir(p):
    if not os.path.exists(p):
        os.makedirs(p)


PRINTABLE_RE = re.compile(rb'[\x20-\x7E]{4,}')  # ascii printable, min length 4

def hexdump(b, length=64):
    return ' '.join(f'{c:02x}' for c in b[:length])

def extract_ascii_strings(b, min_len=4):
    return [m.group().decode('latin1') for m in re.finditer(rb'[\x20-\x7E]{%d,}' % min_len, b)]

def extract_utf16le_strings_with_pos(b, min_chars=2):
    # find (printable byte + \x00) repeated
    pat = re.compile(rb'(?:[\x20-\x7E]\x00){%d,}' % min_chars)
    for m in pat.finditer(b):
        try:
            yield (m.start(), m.group().decode('utf-16le'))
        except Exception:
            continue

def extract_utf16be_strings_with_pos(b, min_chars=2):
    pat = re.compile(rb'(?:\x00[\x20-\x7E]){%d,}' % min_chars)
    for m in pat.finditer(b):
        try:
            yield (m.start(), m.group().decode('utf-16be'))
        except Exception:
            continue

def group_consecutive_strings(strings_with_pos, gap_threshold=8):
    grouped = []
    if not strings_with_pos:
        return grouped
    strings_with_pos = sorted(strings_with_pos, key=lambda x: x[0])
    current = [strings_with_pos[0][1]]
    last_end = strings_with_pos[0][0] + len(strings_with_pos[0][1].encode('utf-16le'))
    for pos, s in strings_with_pos[1:]:
        if pos - last_end <= gap_threshold:
            current.append(s)
        else:
            grouped.append(''.join(current))
            current = [s]
        last_end = pos + len(s.encode('utf-16le'))
    grouped.append(''.join(current))
    return grouped

def find_audio_like(strings):
    exts = ('.wav', '.aiff', '.aif', '.ncw', '.flac', '.ogg', '.mp3')
    out = []
    for s in strings:
        low = s.lower()
        if any(low.endswith(ext) or ext in low for ext in exts):
            out.append(s)
    return out

def scan_chunk_like(b):
    # Look for 4 printable ASCII bytes + 4-byte LE uint length, with length sane.
    n = len(b)
    candidates = []
    for off in range(0, n - 8):
        head = b[off:off + 4]
        if all(32 <= c < 127 for c in head):
            tag = head.decode('latin1')
            length = struct.unpack_from('<I', b, off + 4)[0]
            # sanity checks
            if 0 < length <= n and (off + 8 + length) <= n and length < (n // 2):
                candidates.append((off, tag, length))
    # return unique by offset
    return candidates

def try_safe_decompress_at(b, offset, outpath):
    # try gzip, zlib, lzma, bzip2
    chunk = b[offset:offset + 20000000]  # limit to 20MB for decompression attempts
    results = []
    # gzip: must start with 1f 8b
    if chunk.startswith(b'\x1f\x8b'):
        try:
            out = gzip.decompress(chunk)
            fn = os.path.join(outpath, f'decompressed-gzip-0x{offset:x}.bin')
            open(fn, 'wb').write(out)
            results.append(fn)
        except Exception:
            pass
    # zlib: try generic zlib.decompress (may throw)
    try:
        out = zlib.decompress(chunk)
        fn = os.path.join(outpath, f'decompressed-zlib-0x{offset:x}.bin')
        open(fn, 'wb').write(out)
        results.append(fn)
    except Exception:
        pass
    # lzma/xz
    # xz header (fd 37 7a 58 5a 00)
    if chunk.startswith(b'\xfd7zXZ\x00'):
        try:
            out = lzma.decompress(chunk)
            fn = os.path.join(outpath, f'decompressed-xz-0x{offset:x}.bin')
            open(fn, 'wb').write(out)
            results.append(fn)
        except Exception:
            pass
    # try lzma even if header absent (catch-all)
    try:
        out = lzma.decompress(chunk)
        fn = os.path.join(outpath, f'decompressed-lzma-0x{offset:x}.bin')
        open(fn, 'wb').write(out)
        results.append(fn)
    except Exception:
        pass
    # bzip2 (header 'BZh')
    if chunk.startswith(b'BZh'):
        try:
            out = bz2.decompress(chunk)
            fn = os.path.join(outpath, f'decompressed-bz2-0x{offset:x}.bin')
            open(fn, 'wb').write(out)
            results.append(fn)
        except Exception:
            pass
    return results

def try_decompress_search(b, outpath, scan_step=4096):
    found = []
    n = len(b)
    for off in range(0, n, scan_step):
        # quick header check for common compressions
        if b[off:off + 2] in (b'\x1f\x8b',):  # gzip
            found += try_safe_decompress_at(b, off, outpath)
        if b[off:off + 6] == b'\xfd7zXZ\x00':
            found += try_safe_decompress_at(b, off, outpath)
        if b[off:off + 3] == b'BZh':
            found += try_safe_decompress_at(b, off, outpath)
        # also try zlib at each step (cheap attempt), but guard exceptions
        try:
            # attempt zlib with short sample to avoid crashing on random data
            sample = b[off:off + 1024]
            # attempt only if first two bytes plausible for zlib (not strict)
            if len(sample) >= 2:
                try:
                    _ = zlib.decompress(sample)
                    # if successful, try a bigger decompress
                    found += try_safe_decompress_at(b, off, outpath)
                except Exception:
                    pass
        except Exception:
            pass
    return found

def xor_single_byte_and_extract(b, outpath, min_printable_run=30):
    # brute-force single-byte XOR keys 1..255, write keys that create long printable runs
    n = len(b)
    winners = []
    for key in range(1, 256):
        xb = bytes([c ^ key for c in b])
        # quick check: count printable ascii bytes ratio
        printable = sum(1 for c in xb if 32 <= c <= 126)
        if printable < (n * 0.15):  # require at least 15% printable to consider further
            continue
        # extract printable strings
        runs = [m.group().decode('latin1') for m in re.finditer(rb'[\x20-\x7E]{4,}', xb)]
        if not runs:
            continue
        # if any run is long, write file
        long_runs = [r for r in runs if len(r) >= min_printable_run]
        if long_runs:
            fn = os.path.join(outpath, f'xor-key-{key:02x}.txt')
            with open(fn, 'w', encoding='utf-8') as f:
                f.write(f'XOR key: 0x{key:02x}\n\n')
                for r in runs[:500]:
                    f.write(r + '\n')
            winners.append(fn)
    return winners

def dump_chunks(b, outpath, candidates, max_dumps=200):
    written = []
    count = 0
    for off, tag, length in candidates:
        if count >= max_dumps:
            break
        start = off + 8
        end = start + length
        blob = b[start:end]
        fn = os.path.join(outpath, f'chunk-0x{off:x}-{tag}.bin')
        try:
            with open(fn, 'wb') as fh:
                fh.write(blob)
            written.append(fn)
        except Exception:
            pass
        count += 1
    return written

def decode_full_with_encodings(b, outpath):
    encs = [
        ('utf-16le', 'utf-16le'),
        ('utf-16be', 'utf-16be'),
        ('utf-32le', 'utf-32le'),
        ('utf-32be', 'utf-32be'),
        ('utf-8', 'utf-8'),
        ('latin1', 'latin1'),
        ('cp1252', 'cp1252'),
    ]
    results = []
    for name, enc in encs:
        for start_offset in (0, 1):  # alignment tries
            try:
                dec = b[start_offset:].decode(enc, errors='replace')
                fn = os.path.join(outpath, f'full-decode-{name}-off{start_offset}.txt')
                open(fn, 'w', encoding='utf-8').write(dec)
                results.append(fn)
            except Exception:
                continue
    return results

def extract_utf16_fragments(b, outpath):
    # collect raw fragments with offsets and grouped reconstructions
    fragments = list(extract_utf16le_strings_with_pos(b, min_chars=2))
    with open(os.path.join(outpath, 'utf16le-fragments.txt'), 'w', encoding='utf-8') as f:
        for pos, s in fragments:
            f.write(f'0x{pos:08x}\t{s}\n')
    # grouped variants with different thresholds
    for thr in (2, 4, 8, 16):
        grouped = group_consecutive_strings(fragments, gap_threshold=thr)
        fn = os.path.join(outpath, f'utf16le-grouped-gap{thr}.txt')
        with open(fn, 'w', encoding='utf-8') as f:
            for s in grouped:
                f.write(s + '\n')
    return [os.path.join(outpath, 'utf16le-fragments.txt')] + [
        os.path.join(outpath, f'utf16le-grouped-gap{thr}.txt') for thr in (2, 4, 8, 16)
    ]

def main():
    if len(sys.argv) < 2:
        print("Usage: python nbkt_bruteforce.py /path/to/file.nbkt [outdir]")
        sys.exit(1)
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else './out'
    ensure_dir(outdir)
    with open(path, 'rb') as f:
        data = f.read()
    n = len(data)
    report_lines = []
    report_lines.append(f'File: {os.path.abspath(path)}')
    report_lines.append(f'Size: {n} bytes')
    report_lines.append('Header hex: ' + hexdump(data, 128))
    # quick ascii and utf16 samples
    ascii_sample = extract_ascii_strings(data, min_len=4)[:200]
    report_lines.append(f'ASCII sample (first 200): count={len(ascii_sample)}')
    with open(os.path.join(outdir, 'ascii-sample.txt'), 'w', encoding='utf-8') as f:
        for s in ascii_sample:
            f.write(s + '\n')
    # utf16 fragments + grouped
    report_lines.append('Extracting UTF-16LE fragments and grouped variants...')
    utf16_files = extract_utf16_fragments(data, outdir)
    report_lines += [f'Wrote {x}' for x in utf16_files]
    # full decode with many encodings
    report_lines.append('Decoding full file with multiple encodings (offsets 0 and 1)...')
    full_decodes = decode_full_with_encodings(data, outdir)
    report_lines += [f'Wrote {x}' for x in full_decodes]
    # chunk-like scan and dumps
    report_lines.append('Scanning for chunk-like 4ASCII+u32 patterns...')
    candidates = scan_chunk_like(data)
    report_lines.append(f'Found {len(candidates)} chunk-like candidates (dumping up to 200).')
    chunk_files = dump_chunks(data, outdir, candidates)
    report_lines += [f'Dumped chunk {i+1}: {fn}' for i, fn in enumerate(chunk_files)]
    # search for common compression signatures and attempt decompression
    report_lines.append('Searching for embedded compression signatures and trying decompression (scanning every 4KB)...')
    dec_files = try_decompress_search(data, outdir, scan_step=4096)
    report_lines += [f'Decompressed: {x}' for x in dec_files]
    # XOR brute force single byte
    report_lines.append('Running XOR single-byte brute force (writing keys that produce long printable runs)...')
    xor_files = xor_single_byte_and_extract(data, outdir, min_printable_run=60)
    report_lines += [f'XOR candidate: {x}' for x in xor_files]
    # audio-like detection in grouped utf16 outputs
    report_lines.append('Searching for audio-like filenames in grouped utf16 outputs...')
    audio_candidates = []
    for thr in (2, 4, 8, 16):
        fn = os.path.join(outdir, f'utf16le-grouped-gap{thr}.txt')
        if os.path.exists(fn):
            txt = open(fn, 'r', encoding='utf-8', errors='ignore').read().splitlines()
            found = find_audio_like(txt)
            if found:
                audio_candidates += found
                outfn = os.path.join(outdir, f'audio-like-gap{thr}.txt')
                open(outfn, 'w', encoding='utf-8').write('\n'.join(found))
                report_lines.append(f'Found {len(found)} audio-like items in {fn} -> {outfn}')
    # write final report
    rpt = os.path.join(outdir, 'report.txt')
    with open(rpt, 'w', encoding='utf-8') as f:
        for L in report_lines:
            f.write(L + '\n')
    # echo short summary to stdout
    print('--- Done. Summary ---')
    for L in report_lines[:20]:
        print(L)
    print('Wrote report to:', rpt)
    print('Out directory:', os.path.abspath(outdir))


if __name__ == '__main__':
    main()
