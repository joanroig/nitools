def extract_ascii_strings(input_file, output_file):
    with open(input_file, "rb") as f:
        data = f.read()

    text_chunks = []
    for chunk in data.split(b'\x00'):  # split by null bytes
        try:
            s = chunk.decode('ascii').strip()
            # Filter out empty or mostly non-printable chunks
            if s and all(32 <= ord(c) <= 126 for c in s):
                text_chunks.append(s)
        except UnicodeDecodeError:
            # Ignore chunks that can't be decoded as ASCII
            continue

    with open(output_file, "w", encoding="utf-8") as f:
        for line in text_chunks:
            f.write(line + "\n")

# Usage example
extract_ascii_strings("Akwaaba Kit.nbkt", "clean_output.txt")