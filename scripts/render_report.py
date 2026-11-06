"""Render report/report.md -> report/report.pdf (pure-Python, no system deps).

    pip install markdown xhtml2pdf
    python scripts/render_report.py

Regenerate this after filling the cluster-run numbers (Task 3 image size, Task 4 reliability,
Task 7 load test) into report/report.md. The built-in PDF fonts lack glyphs for some symbols, so a
few Unicode characters are mapped to ASCII before rendering.
"""
import os
import sys

import markdown
from xhtml2pdf import pisa

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "report", "report.md")
OUT = os.path.join(ROOT, "report", "report.pdf")

SUBST = {
    "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~=",
    "×": "x", "—": " - ", "–": "-", "·": " - ", "…": "...",
    "‘": "'", "’": "'", "“": '"', "”": '"', " ": " ",
    "‑": "-", "₹": "INR ", "✓": "[ok]",
}

CSS = """
@page { size: A4; margin: 1.5cm 1.6cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10px; line-height: 1.35; color: #111; }
h1 { font-size: 17px; margin: 0 0 6px 0; }
h2 { font-size: 13px; margin: 12px 0 4px 0; border-bottom: 1px solid #bbb; padding-bottom: 2px; }
h3 { font-size: 11px; margin: 8px 0 3px 0; }
p  { margin: 4px 0; }
code, pre { font-family: Courier, monospace; font-size: 8.5px; background: #f4f4f4; }
pre { padding: 5px; border: 1px solid #ddd; }
table { width: 100%; margin: 5px 0; font-size: 8.5px; }
th, td { border: 1px solid #999; padding: 2px 4px; text-align: left; }
th { background: #eee; }
a { color: #1256a0; text-decoration: none; }
"""


def main():
    raw = open(SRC, encoding="utf-8").read()
    for a, b in SUBST.items():
        raw = raw.replace(a, b)
    # Drop the author-only "Convention / delete before export" blockquote note.
    text = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith(">"))
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    with open(OUT, "wb") as f:
        result = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    if result.err:
        sys.exit("PDF generation failed")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
