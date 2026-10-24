"""Builds the source-code appendix (Appendix F): every source file of the project, with line numbers.

    report/.venv/Scripts/python.exe report/build_code_appendix.py

Output: report/build/GoalWise_Source_Code.pdf (A4, Courier New 7.5 pt, a contents list of files
with their page numbers). Files come from `git ls-files`, in the order of Appendix F's table.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "build" / "GoalWise_Source_Code.pdf"
FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "times.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONTS / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "cour.ttf")))
pdfmetrics.registerFont(TTFont("Mono-Bold", str(FONTS / "courbd.ttf")))
MONO_CMAP = set(pdfmetrics.getFont("Mono").face.charToGlyph)

PAGE_W, PAGE_H = A4
LEFT, RIGHT, TOP, BOTTOM = 1.5 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch
TEXT_W = PAGE_W - LEFT - RIGHT
CODE_SIZE = 7.5
code = ParagraphStyle("code", fontName="Mono", fontSize=CODE_SIZE, leading=9)
file_head = ParagraphStyle("fh", fontName="Mono-Bold", fontSize=9.5, leading=12, spaceBefore=4,
                           spaceAfter=4)
title = ParagraphStyle("t", fontName="Body-Bold", fontSize=18, leading=24, alignment=1,
                       spaceAfter=10)
part_head = ParagraphStyle("ph", fontName="Body-Bold", fontSize=13, leading=18, spaceBefore=6,
                           spaceAfter=6)
toc = ParagraphStyle("toc", fontName="Mono", fontSize=7.5, leading=9.4)
note = ParagraphStyle("n", fontName="Body", fontSize=11, leading=15)

# Parts in the order of Appendix F (prefix match on the repository path).
PARTS = [
    ("Backend: core", ["backend/app/__init__.py", "backend/app/main.py", "backend/app/core/"]),
    ("Backend: models", ["backend/app/models/"]),
    ("Backend: schemas", ["backend/app/schemas/"]),
    ("Backend: API routes", ["backend/app/api/"]),
    ("Backend: services", ["backend/app/services/"]),
    ("Backend: finance", ["backend/app/finance/"]),
    ("Backend: simulation", ["backend/app/simulation/"]),
    ("Backend: data pipeline", ["backend/app/data_pipeline/"]),
    ("Backend: machine learning", ["backend/app/ml/"]),
    ("Backend: recommendation", ["backend/app/recommendation/"]),
    ("Backend: portfolio", ["backend/app/portfolio/"]),
    ("Backend: chatbot", ["backend/app/chatbot/"]),
    ("Backend: reports, evaluation, deployment, admin",
     ["backend/app/reports/", "backend/app/evaluation/", "backend/app/deploy/",
      "backend/app/frontend.py", "backend/app/admin.py"]),
    ("Backend: database migrations", ["backend/alembic/"]),
    ("Backend: tests", ["backend/tests/"]),
    ("Frontend: application", ["frontend/src/", "frontend/index.html"]),
    ("Frontend: end-to-end tests", ["frontend/e2e/"]),
    ("Configuration", ["backend/pyproject.toml", "backend/alembic.ini", "backend/.env.example",
                       "backend/Dockerfile", "backend/.dockerignore", "docker-compose.yml",
                       "render.yaml", "frontend/vercel.json", "frontend/package.json",
                       "frontend/vite.config.ts", "frontend/playwright.config.ts",
                       "frontend/tsconfig.json", "frontend/tsconfig.app.json",
                       "frontend/tsconfig.node.json", ".github/workflows/"]),
]
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".css", ".html", ".toml", ".ini", ".yml", ".yaml",
                   ".json", ".example", "Dockerfile", ".dockerignore")
SKIP = ("knowledge/", "chatbot_questions.json", "package-lock.json", "uv.lock")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.split("\n")
    return [f for f in out if f and f.endswith(SOURCE_SUFFIXES) and not any(s in f for s in SKIP)]


def grouped() -> list[tuple[str, list[str]]]:
    files = tracked_files()
    used: set[str] = set()
    groups = []
    for name, prefixes in PARTS:
        chosen = []
        for prefix in prefixes:
            matches = sorted(f for f in files if (f == prefix or f.startswith(prefix))
                             and f not in used)
            chosen += matches
            used.update(matches)
        if chosen:
            groups.append((name, chosen))
    return groups


def _escape(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "".join(ch if ord(ch) in MONO_CMAP or ch == "\n" else "?" for ch in text)


class FileStart(Flowable):
    width = height = 0

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def draw(self):
        pass


class CodeDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(filename, pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT, topMargin=TOP,
                         bottomMargin=BOTTOM, title="GoalWise – Source Code (Appendix F)")
        frame = Frame(LEFT, BOTTOM, TEXT_W, PAGE_H - TOP - BOTTOM, leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="p", frames=[frame], onPageEnd=self.footer)])
        self.starts: dict[str, int] = {}
        self.current = ""

    def footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Body", 9)
        canvas.drawString(LEFT, 0.45 * inch, "GoalWise – Appendix F: Source code")
        canvas.drawRightString(PAGE_W - RIGHT, 0.45 * inch, f"F-{doc.page}")
        if self.current:
            canvas.setFont("Mono", 7)
            canvas.drawRightString(PAGE_W - RIGHT, PAGE_H - 0.5 * inch, self.current)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, FileStart):
            self.starts[flowable.path] = self.page
            self.current = flowable.path


def file_flowables(path: str) -> list:
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace").expandtabs(4)
    lines = text.rstrip("\n").split("\n")
    width = int(TEXT_W / (CODE_SIZE * 0.6)) - 7  # characters per line after the number
    numbered = []
    for n, line in enumerate(lines, start=1):
        first = True
        while True:
            part, line = line[:width], line[width:]
            numbered.append(f"{n:5d}  {part}" if first else f"       {part}")
            first = False
            if not line:
                break
    out: list = [FileStart(path), Paragraph(_escape(f"{path}  ({len(lines)} lines)"), file_head)]
    # Chunks of 60 lines, so a long file can break across pages.
    for k in range(0, len(numbered), 60):
        out.append(XPreformatted(_escape("\n".join(numbered[k:k + 60])), code))
    out.append(Spacer(1, 8))
    return out


def build(starts: dict[str, int] | None) -> CodeDoc:
    groups = grouped()
    story: list = [
        Paragraph("APPENDIX F", title),
        Paragraph("SOURCE CODE OF GOALWISE (VERSION 1.2.0)", title),
        Paragraph(
            "This volume contains every source file of the final release: the backend (Python), "
            "the database migrations, the frontend (TypeScript and React), the automated tests and "
            "the configuration for building, testing and deployment. Data files (the knowledge-base "
            "articles, the evaluation questions, lock files) are not printed. Each file is shown "
            "with its path and line numbers; long lines continue on the next line without a number.",
            note),
        Spacer(1, 10),
    ]
    total_lines = 0
    rows = []
    for name, files in groups:
        rows.append([Paragraph(f"<b>{name}</b>", ParagraphStyle("g", parent=toc,
                                                               fontName="Mono-Bold")), ""])
        for f in files:
            page = f"F-{starts[f]}" if starts and f in starts else "F-000"
            rows.append([Paragraph(_escape("  " + f), toc), Paragraph(page, toc)])
            total_lines += len((ROOT / f).read_text(encoding="utf-8", errors="replace")
                               .rstrip("\n").split("\n"))
    contents = Table(rows, colWidths=[TEXT_W - 50, 50], repeatRows=0)
    contents.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                                  ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
    story += [Paragraph(f"Contents: {sum(len(f) for _, f in groups)} files, {total_lines:,} lines",
                        part_head), contents]
    for name, files in groups:
        story += [PageBreak(), Paragraph(name, part_head)]
        for f in files:
            story += file_flowables(f)
    doc = CodeDoc(str(OUTPUT))
    doc.build(story)
    return doc


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    first = build(None)
    second = build(first.starts)
    if second.starts != first.starts:
        second = build(second.starts)
    print(f"{OUTPUT.name}: {second.page} pages, {len(second.starts)} files")


if __name__ == "__main__":
    main()
