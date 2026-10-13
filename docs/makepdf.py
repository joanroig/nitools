import sys
import os
from urllib.parse import unquote

import pymupdf
from markdown_pdf import MarkdownPdf, Section

if len(sys.argv) < 3:
    sys.exit("Usage: script.py <input.md> <output.pdf>")

md_filepath = sys.argv[1]
pdf_filepath = sys.argv[2]

# Create PDF with table of contents up to level 4
pdf = MarkdownPdf(toc_level=4, optimize=True)

# Resolve relative paths for images/links
root = os.path.dirname(os.path.abspath(md_filepath))

# MuPDF otherwise shrinks screenshots to whatever space remains on a page.
# Reserve their full height so an image moves intact to the next page.
render_image = pdf.m_d.renderer.rules['image']


def sized_image(tokens, index, options, env):
    token = tokens[index]
    path = os.path.join(root, unquote(token.attrGet('src')))
    pixmap = pymupdf.Pixmap(path)
    width = min(500, pixmap.width)
    height = width * pixmap.height / pixmap.width
    token.attrSet('style', f'width:{width}pt; height:{height}pt')
    image = render_image(tokens, index, options, env)
    return f'<div style="height:{height + 6}pt; page-break-inside:avoid">{image}</div>'


pdf.m_d.renderer.rules['image'] = sized_image

# Read Markdown content
with open(md_filepath, encoding="utf-8") as f:
    content = f.read()

# Add content
pdf.add_section(Section(content, root=root), user_css="""
    body { font-family: sans-serif; font-size: 10pt; }
    h1, h2, h3, h4 { page-break-after: avoid; }
    p { page-break-inside: avoid; }
""")
pdf.meta["title"] = "NITools Guide"

# Save
pdf.save(pdf_filepath)
