import sys
import os
from markdown_pdf import MarkdownPdf, Section

if len(sys.argv) < 3:
    sys.exit("Usage: script.py <input.md> <output.pdf>")

md_filepath = sys.argv[1]
pdf_filepath = sys.argv[2]

# Create PDF with table of contents up to level 4
pdf = MarkdownPdf(toc_level=4)

# Resolve relative paths for images/links
root = os.path.dirname(os.path.abspath(md_filepath))

# Read Markdown content
with open(md_filepath, encoding="utf-8") as f:
    content = f.read()

# Add content
pdf.add_section(Section(content, root=root))
pdf.meta["title"] = "NITools Guide"

# Save
pdf.save(pdf_filepath)
