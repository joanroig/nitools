import re

def extract_clean_strings(input_file, output_file, min_length=4):
    with open(input_file, "rb") as f:
        data = f.read()

    # Use regex to extract ASCII strings of at least min_length characters
    pattern = re.compile(b'[\x20-\x7E]{%d,}' % min_length)
    matches = pattern.findall(data)

    clean_strings = []
    for m in matches:
        s = m.decode('ascii')
        # Filter strings with too many special chars (>30%)
        special_chars = sum(not c.isalnum() and c not in ' _-.:/@' for c in s)
        if special_chars / len(s) <= 0.3:
            clean_strings.append(s)

    with open(output_file, "w", encoding="utf-8") as f:
        for line in clean_strings:
            f.write(line + "\n")

# Usage example
extract_clean_strings("Akwaaba Kit.nbkt", "clean_output.txt")