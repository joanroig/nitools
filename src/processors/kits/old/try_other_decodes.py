import unicodedata
import string
import re
import zlib
import gzip
import bz2
import lzma
import os

# Try different decompression methods
def try_decompress_all(data):
    decompressors = {
        'zlib': lambda d: zlib.decompress(d),
        'gzip': lambda d: gzip.decompress(d),
        'bz2': lambda d: bz2.decompress(d),
        'lzma': lambda d: lzma.decompress(d),
    }

    results = {}
    for name, func in decompressors.items():
        try:
            results[name] = func(data)
            print(f"[✓] Decompressed using {name}")
        except Exception:
            print(f"[✗] {name} decompression failed")
            results[name] = None
    return results


def extract_clean_strings(data, encoding, min_length=4):
    try:
        if isinstance(data, bytes):
            decoded = data.decode(encoding, errors='ignore').replace('\u00A0', ' ').replace('\u200B', ' ')

        # Extract sequences of printable words (letters, numbers, common symbols, space)
        matches = re.findall(r'[\w \-.:/@#]{%d,}' % min_length, decoded)

        clean_strings = []
        for s in matches:
            s = ' '.join(s.split())  # Normalize internal whitespace to single space
            special_chars = sum(not c.isalnum() and c not in ' _-.:/@#' for c in s)
            if len(s) > 0 and special_chars / len(s) <= 0.3:
                clean_strings.append(s.strip())
        return clean_strings

    except Exception as e:
        print(f"Error decoding with {encoding}: {e}")
        return []


# Main processing logic
def decrypt_and_compare(input_file, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    with open(input_file, "rb") as f:
        data = f.read()

    # Original binary
    decompressed_variants = try_decompress_all(data)
    decompressed_variants['raw'] = data  # include raw version

    encodings = ['ascii', 'utf-8', 'latin-1', 'utf-16']

    for method, variant in decompressed_variants.items():
        if variant is None:
            continue
        for encoding in encodings:
            strings = extract_clean_strings(variant, encoding)
            if strings:
                out_file = f"{output_folder}/clean_{method}_{encoding}.txt"
                with open(out_file, "w", encoding="utf-8") as out:
                    out.write("\n".join(strings))
                print(f"[+] Written {len(strings)} strings to {out_file}")


if __name__ == "__main__":
    decrypt_and_compare("kits/Aquamarine Kit.nbkt", "out/battery")
