import sys
import zlib
import re

def extract_strings(data, min_length=4):
    """Extract readable ASCII strings from binary data."""
    strings = []
    current = b""
    for b in data:
        if 32 <= b < 127:
            current += bytes([b])
        else:
            if len(current) >= min_length:
                strings.append(current.decode('utf-8', errors='ignore'))
            current = b""
    if len(current) >= min_length:
        strings.append(current.decode('utf-8', errors='ignore'))
    return strings

def try_decompress(data):
    """Try full zlib decompression."""
    try:
        return zlib.decompress(data)
    except:
        return None

def find_zlib_chunks(data):
    """Find possible zlib headers in the binary data."""
    return [i for i in range(len(data) - 2) if data[i] == 0x78 and data[i+1] == 0x9C]

def group_strings(strings):
    """Group sequences of readable strings."""
    grouped = []
    block = []
    for s in strings:
        if any(c.isalnum() for c in s):
            block.append(s)
        else:
            if block:
                grouped.append(block)
                block = []
    if block:
        grouped.append(block)
    return grouped

def filter_keywords(strings, keywords):
    """Return strings matching any keyword."""
    return [s for s in strings if any(k in s.lower() for k in keywords)]

def extract_sample_paths(strings):
    """Detect file paths likely pointing to samples."""
    return [s for s in strings if re.search(r'\.(wav|aif|flac|ogg|mp3)', s.lower())]

def read_nbkt_file(path):
    with open(path, 'rb') as f:
        raw = f.read()

    print(f"[+] Loaded file: {path} ({len(raw)} bytes)\n")

    # Try decompressing the whole file
    all_strings = []
    decompressed = try_decompress(raw)
    if decompressed:
        print("[+] Full file decompressed via zlib.")
        all_strings += extract_strings(decompressed)
    else:
        print("[!] Full file not zlib-decodable. Scanning embedded zlib chunks...")

    # Try embedded zlib blocks
    zlib_offsets = find_zlib_chunks(raw)
    print(f"[+] Found {len(zlib_offsets)} zlib header(s).")
    for offset in zlib_offsets:
        try:
            sub = raw[offset:]
            out = zlib.decompress(sub)
            strings = extract_strings(out)
            all_strings += strings
            print(f"[+] Decompressed chunk at offset {offset} ({len(strings)} strings)")
        except:
            continue

    # Fallback: extract from raw data if nothing else worked
    if not all_strings:
        all_strings = extract_strings(raw)

    print(f"\n[+] Total extracted strings: {len(all_strings)}\n")

    # Find and print sample file paths
    sample_paths = extract_sample_paths(all_strings)
    if sample_paths:
        print("[+] Detected sample paths:\n")
        for s in sample_paths:
            print("   ", s)
        print("\n---\n")

    # Find and print relevant keywords
    KEYWORDS = ['sample', 'note', 'velocity', 'gain', 'mute', 'attack',
                'decay', 'release', 'filter', 'fx', 'trigger', 'pad',
                'curve', 'fade', 'loop', 'duration', 'mod', 'random', 'slot']
    matches = filter_keywords(all_strings, KEYWORDS)
    if matches:
        print("[+] Keyword matches:\n")
        for s in matches:
            print("   ", s)
        print("\n---\n")

    # Print grouped string blocks
    print("[+] Grouped string blocks:\n")
    for i, block in enumerate(group_strings(all_strings)):
        print(f"Block {i+1}:")
        for line in block:
            print("   ", line)
        print("---\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python nbkt_reader.py path/to/file.nbkt")
        sys.exit(1)

    read_nbkt_file(sys.argv[1])
