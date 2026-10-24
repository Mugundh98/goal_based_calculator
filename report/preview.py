"""Renders pages of a PDF to PNG for checking the layout.

    report/.venv/Scripts/python.exe report/preview.py build/GoalWise_Project_Report.pdf 1 5 12
    (page numbers are 1-based physical pages; "all" renders every page; images go to build/preview/)
"""

import sys
from pathlib import Path

import fitz  # PyMuPDF

pdf = Path(sys.argv[1])
out = pdf.parent / "preview"
out.mkdir(exist_ok=True)
doc = fitz.open(pdf)
pages = range(1, doc.page_count + 1) if sys.argv[2:] == ["all"] else [int(p) for p in sys.argv[2:]]
zoom = 0.9
for n in pages:
    pix = doc[n - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    target = out / f"{pdf.stem[:12]}-p{n:03d}.png"
    pix.save(target)
    print(target)
