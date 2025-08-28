import json

# Sort the UPIDs in upids.txt by the part after the first space
# UPIDs are in the format: <UPID> <Description>
# Initial dump retrieved with Native Access Product Report from https://bobdule999.wixsite.com/librarytools/extra

# Read lines from the file
with open("docs/upids/upids.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Remove trailing newlines
lines = [line.rstrip("\n") for line in lines]

# Sort by the part after the first space (the description)
sorted_lines = sorted(lines, key=lambda x: x.split(' ', 1)[1])

# Build a dictionary {UPID: Description}
upid_dict = {line.split(' ', 1)[0]: line.split(' ', 1)[1] for line in sorted_lines}

# Export to JSON
with open("resources/upids.json", "w", encoding="utf-8") as f:
    json.dump(upid_dict, f, ensure_ascii=False, indent=4)
