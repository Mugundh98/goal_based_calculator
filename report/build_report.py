"""Builds the MCA project report (PDF) from Markdown chapters and the project's own documents.

    report/.venv/Scripts/python.exe report/build_report.py

Inputs
  report/details.json      the learner's and guide's details (blank = a line to fill by hand)
  report/chapters/*.md     the chapters, in file-name order (00-* are front matter)
  docs/**                  sections pulled in with  <!-- include: docs/phases/05-simulation.md
                           sections="Key logic explained" level=3 -->

Markdown subset: # chapter, ## section, ### subsection, #### run-in heading; paragraphs; - and 1.
lists (nested by indentation); | tables | (a "Table: caption" line just before); ``` code;
```mermaid diagrams and ```latex formulas (rendered by render_assets.js); ![caption](image);
"Figure: caption" just after a diagram or image; **bold**, *italic*, `code`, [text](url).

Output: report/build/GoalWise_Project_Report.pdf, and a page count per chapter on the console.
Layout: A4, Times New Roman 12 pt, double-spaced body, margins 1.5 in left (binding) and 1 in
elsewhere; front matter numbered i, ii, ...; chapters numbered from 1.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
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
BUILD = HERE / "build"
ASSETS = BUILD / "assets"
OUTPUT = BUILD / "GoalWise_Project_Report.pdf"

PAGE_W, PAGE_H = A4
LEFT, RIGHT, TOP, BOTTOM = 1.5 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch
TEXT_W = PAGE_W - LEFT - RIGHT
TEXT_H = PAGE_H - TOP - BOTTOM

# --- Fonts -----------------------------------------------------------------------------------

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "times.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONTS / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONTS / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", str(FONTS / "timesbi.ttf")))
pdfmetrics.registerFontFamily(
    "Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic"
)
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "cour.ttf")))
pdfmetrics.registerFont(TTFont("Mono-Bold", str(FONTS / "courbd.ttf")))
pdfmetrics.registerFontFamily(
    "Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold"
)
pdfmetrics.registerFont(TTFont("Symbols", str(FONTS / "seguisym.ttf")))

_BODY_CMAP = set(pdfmetrics.getFont("Body").face.charToGlyph)
_MONO_CMAP = set(pdfmetrics.getFont("Mono").face.charToGlyph)
_SYMBOL_CMAP = set(pdfmetrics.getFont("Symbols").face.charToGlyph)

# --- Styles ----------------------------------------------------------------------------------

BODY_SIZE, BODY_LEADING = 12, 24  # double spacing
body = ParagraphStyle(
    "body", fontName="Body", fontSize=BODY_SIZE, leading=BODY_LEADING, alignment=TA_JUSTIFY,
    spaceAfter=6,
)
body_left = ParagraphStyle("body_left", parent=body, alignment=TA_LEFT)
list_text = ParagraphStyle("list", parent=body, alignment=TA_LEFT, spaceAfter=0)
quote = ParagraphStyle("quote", parent=body, leftIndent=24, fontName="Body-Italic")
cell = ParagraphStyle("cell", fontName="Body", fontSize=10, leading=12.5, alignment=TA_LEFT)
cell_head = ParagraphStyle("cell_head", parent=cell, fontName="Body-Bold")
small_cell = ParagraphStyle("small_cell", parent=cell, fontSize=9, leading=11)
small_head = ParagraphStyle("small_head", parent=small_cell, fontName="Body-Bold")
caption = ParagraphStyle(
    "caption", fontName="Body-Bold", fontSize=11, leading=14, alignment=TA_CENTER,
    spaceBefore=4, spaceAfter=12,
)
code_style = ParagraphStyle("code", fontName="Mono", fontSize=8.3, leading=10.2)
h_chapter_no = ParagraphStyle(
    "chapno", fontName="Body-Bold", fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=6
)
h_chapter = ParagraphStyle(
    "chap", fontName="Body-Bold", fontSize=18, leading=24, alignment=TA_CENTER, spaceAfter=24
)
h2 = ParagraphStyle("h2", fontName="Body-Bold", fontSize=14, leading=20, spaceBefore=14,
                    spaceAfter=6)
h3 = ParagraphStyle("h3", fontName="Body-Bold", fontSize=12.5, leading=18, spaceBefore=10,
                    spaceAfter=4)
h4 = ParagraphStyle("h4", fontName="Body-BoldItalic", fontSize=12, leading=18, spaceBefore=6,
                    spaceAfter=2)
center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
display = ParagraphStyle("display", parent=body, alignment=TA_CENTER, leading=20, spaceAfter=2)
toc_1 = ParagraphStyle("toc1", fontName="Body-Bold", fontSize=11.5, leading=17)
toc_2 = ParagraphStyle("toc2", fontName="Body", fontSize=11, leading=15, leftIndent=18)
toc_3 = ParagraphStyle("toc3", fontName="Body", fontSize=10.5, leading=14, leftIndent=40)

# --- Inline markdown -> ReportLab markup -----------------------------------------------------


def _fallback(text: str, cmap: set[int]) -> str:
    """Characters the main font lacks are drawn in Segoe UI Symbol."""
    out = []
    for ch in text:
        if ord(ch) in cmap or ch in "\n\t" or ord(ch) < 32:
            out.append(ch)
        elif ord(ch) in _SYMBOL_CMAP:
            out.append(f'<font name="Symbols">{ch}</font>')
        else:
            out.append("?")
    return "".join(out)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str, cmap: set[int] = _BODY_CMAP) -> str:
    """Markdown inline formatting to ReportLab paragraph markup."""
    codes: list[str] = []

    def keep_code(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)  # stray images: keep the words
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)  # links: keep the words
    text = re.sub(r"<br\s*/?>", " ", text)
    text = _escape(text)
    text = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"<super>\1</super>", text)
    text = re.sub(r"(?<=[A-Za-z\u0370-\u03ff])_([A-Za-z0-9])(?![\w])", r"<sub>\1</sub>", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])", r"<i>\1</i>", text)
    text = _fallback(text, cmap)

    def put_code(m: re.Match) -> str:
        code = _fallback(_escape(codes[int(m.group(1))]), _MONO_CMAP)
        return f'<font name="Mono">{code}</font>'

    return re.sub(r"\x00(\d+)\x00", put_code, text)


def P(markup: str, style: ParagraphStyle) -> Paragraph:
    """A Paragraph; if nested emphasis came out malformed, the same text without emphasis."""
    try:
        return Paragraph(markup, style)
    except ValueError:
        return Paragraph(re.sub(r"</?[bi]>", "", markup), style)


def plain(text: str) -> str:
    """Markdown inline text without formatting (for headings in the contents)."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("*", "")


# --- Markdown blocks -------------------------------------------------------------------------


@dataclass
class Block:
    kind: str  # heading, para, list, table, code, mermaid, latex, image, quote, pagebreak
    text: str = ""
    level: int = 0
    items: list = field(default_factory=list)  # list: [(depth, ordered, text)]; table: rows
    lang: str = ""
    caption: str = ""
    base: Path | None = None  # folder of the source file (images)


FIGURES = ("mermaid", "image", "imagegrid")
INCLUDE = re.compile(r"<!--\s*include:\s*(\S+)(.*?)-->", re.S)


def _include(directive: re.Match) -> str:
    path, args = directive.group(1), directive.group(2)
    opts = dict(re.findall(r'(\w+)="([^"]*)"', args))
    opts.update(re.findall(r"(\w+)=(\d+)", args))
    source = (ROOT / path).read_text(encoding="utf-8")
    # The example goal was renamed in the application (v1.1); keep the report consistent.
    source = source.replace("Ananya", "Pisai")
    sep = "|" if "|" in opts.get("sections", "") else ","
    wanted = [s.strip().lower() for s in opts.get("sections", "").split(sep) if s.strip()]
    level = int(opts.get("level", 3))
    drop = [s.strip().lower() for s in opts.get("drop", "").split("|") if s.strip()]
    chunks = re.split(r"^(?=## )", source, flags=re.M)
    picked = []
    if "preamble" in wanted:  # the text before the first "## " (minus title and status line)
        lead = re.sub(r"^# .*\n", "", chunks[0])
        lead = re.sub(r"^_Living document.*_\s*$", "", lead, flags=re.M)
        picked.append(lead)
    for chunk in chunks:
        if not chunk.startswith("## "):
            continue
        title = re.sub(r"^\d+(\.\d+)*\.?\s*", "", chunk[3:].split("\n", 1)[0]).strip()
        if wanted and title.lower() not in wanted:
            continue
        body_text = chunk.split("\n", 1)[1] if "\n" in chunk else ""
        if opts.get("heading", "keep") == "none":
            out = body_text
        else:
            out = f"{'#' * level} {opts.get('title', title) if len(wanted) == 1 else title}\n{body_text}"
        # Shift the sub-headings under the new level and drop their old numbers.
        def shift(m: re.Match) -> str:
            hashes, name = m.group(1), m.group(2)
            new = min(len(hashes) - 2 + level, 5)
            name = re.sub(r"^\d+(\.\d+)*\.?\s+", "", name)
            if name.strip().lower() in drop:
                return "\x01DROP\x01"
            return f"{'#' * new} {name}"

        out = re.sub(r"^(###+)\s+(.*)$", shift, out, flags=re.M)
        # Drop a whole sub-section marked for dropping (up to the next heading of its level).
        while "\x01DROP\x01" in out:
            start = out.index("\x01DROP\x01")
            nxt = re.search(r"^#{1,%d} " % (level + 1), out[start + 7:], flags=re.M)
            end = start + 7 + nxt.start() if nxt else len(out)
            out = out[:start] + out[end:]
        # Images are relative to the included file.
        base = (ROOT / path).parent
        out = re.sub(
            r"!\[([^\]]*)\]\((?!https?:)([^)]+)\)",
            lambda m: f"![{m.group(1)}]({(base / m.group(2)).resolve().as_posix()})",
            out,
        )
        picked.append(out)
    return "\n\n".join(picked)


def parse(markdown: str, base: Path) -> list[Block]:
    markdown = INCLUDE.sub(_include, markdown)
    markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.S)
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    pending_caption = ""
    pending_figure = ""
    while i < len(lines):
        if pending_figure and blocks and blocks[-1].kind in FIGURES and not blocks[-1].caption:
            blocks[-1].caption, pending_figure = pending_figure, ""
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped in ("---", "***"):
            i += 1
            continue
        if stripped == "\\newpage":
            blocks.append(Block("pagebreak"))
            i += 1
            continue
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            j = i + 1
            code_lines = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            kind = lang if lang in ("mermaid", "latex") else "code"
            source = "\n".join(code_lines)
            if kind == "mermaid":  # a label starting with "/" reads as a shape: quote it
                source = re.sub(r'\[(/[^\]"]*)\]', r'["\1"]', source)
                if source.lstrip().startswith("sequenceDiagram"):
                    source = source.replace(";", ",")  # ";" ends a statement in Mermaid
            blocks.append(Block(kind, source, lang=lang, base=base))
            i = j + 1
            continue
        m = re.match(r"^(#{1,5})\s+(.*)$", stripped)
        if m:
            blocks.append(Block("heading", m.group(2).strip(), level=len(m.group(1))))
            i += 1
            continue
        if stripped.startswith("Table:"):
            pending_caption = stripped[6:].strip()
            i += 1
            continue
        if stripped.startswith("Figure:"):
            # Right after a figure: its caption. Otherwise: the caption of the next figure.
            text = stripped[7:].strip()
            if blocks and blocks[-1].kind in FIGURES and not blocks[-1].caption:
                blocks[-1].caption = text
            else:
                pending_figure = text
            i += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip().strip("|")
                cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            images = [c for r in rows for c in r if c]
            if images and all(re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", c) for c in images):
                blocks.append(Block("imagegrid", items=images, caption=pending_caption, base=base))
            else:
                blocks.append(Block("table", items=rows, caption=pending_caption))
            pending_caption = ""
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)(.*)$", stripped)
        if m:
            blocks.append(Block("image", m.group(2), caption=m.group(1), base=base))
            if m.group(3).strip():
                blocks.append(Block("para", m.group(3).strip()))
            i += 1
            continue
        if re.match(r"^(\s*)([-*+]|\d+[.)])\s+", line):
            items = []
            while i < len(lines):
                cur = lines[i]
                lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", cur)
                if lm:
                    depth = len(lm.group(1).replace("\t", "    ")) // 2
                    items.append([depth, lm.group(2)[0].isdigit(), lm.group(3)])
                    i += 1
                elif cur.strip() and (cur.startswith("  ") or cur.startswith("\t")) and items:
                    items[-1][2] += " " + cur.strip()
                    i += 1
                elif not cur.strip() and i + 1 < len(lines) and re.match(
                    r"^(\s*)([-*+]|\d+[.)])\s+", lines[i + 1]
                ):
                    i += 1
                else:
                    break
            blocks.append(Block("list", items=items))
            continue
        if line.startswith("  ") and not re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            blocks.append(Block("display", stripped))
            i += 1
            continue
        if stripped.startswith(">"):
            text = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                text.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Block("quote", " ".join(text)))
            continue
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", "```", "!", ">", "Table:", "Figure:"))
                    or re.match(r"^([-*+]|\d+[.)])\s+", nxt)):
                break
            para.append(nxt)
            i += 1
        blocks.append(Block("para", " ".join(para)))
    return blocks


# --- Rendered assets (diagrams, formulas) ----------------------------------------------------


def asset_id(kind: str, source: str) -> str:
    return hashlib.sha1(f"{kind}\n{source}".encode()).hexdigest()[:16]


WIDE = 3.2  # a diagram wider than this ratio is drawn top-to-bottom if it is a flowchart


def top_down(source: str) -> str | None:
    """The same flowchart drawn top-to-bottom, or None if it is not a left-to-right one."""
    first, _, rest = source.lstrip().partition("\n")
    m = re.match(r"^(flowchart|graph)\s+LR\b", first.strip())
    return f"{m.group(1)} TB\n{rest}" if m else None


def _run_jobs(jobs: list[dict]) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    result = subprocess.run(["node", str(HERE / "render_assets.js"), str(ASSETS / "jobs.json")],
                            capture_output=True, text=True)
    sys.stdout.write(result.stdout[-2000:])
    if result.returncode:
        sys.stdout.write(result.stderr[-4000:])


def render_assets(all_blocks: list[Block]) -> None:
    jobs = [{"id": asset_id(b.kind, b.text), "kind": b.kind, "source": b.text}
            for b in all_blocks if b.kind in ("mermaid", "latex")]
    _run_jobs(jobs)
    variants = []
    for b in all_blocks:
        if b.kind != "mermaid":
            continue
        png = ASSETS / f"{asset_id('mermaid', b.text)}.png"
        tb = top_down(b.text)
        if png.exists() and tb:
            with PILImage.open(png) as im:
                if im.size[0] / im.size[1] > WIDE:
                    variants.append({"id": asset_id("mermaid", tb), "kind": "mermaid",
                                     "source": tb})
    if variants:
        _run_jobs(variants)


def diagram_png(source: str) -> Path | None:
    """The rendered diagram: its top-to-bottom version when the original is very wide."""
    png = ASSETS / f"{asset_id('mermaid', source)}.png"
    if not png.exists():
        return None
    tb = top_down(source)
    if tb:
        alt = ASSETS / f"{asset_id('mermaid', tb)}.png"
        with PILImage.open(png) as im:
            if im.size[0] / im.size[1] > WIDE and alt.exists():
                return alt
    return png


def fitted_diagram(png: Path) -> Image:
    """Scale a diagram to the text column; rotate a wide, dense one onto the page's length."""
    with PILImage.open(png) as im:
        w_px, h_px = im.size
    natural_w = w_px * 0.3  # pt at the rendered scale
    if natural_w > TEXT_W * 1.6 and w_px / h_px > 1.25:
        rotated = png.with_name(png.stem + "-rot.png")
        if not rotated.exists():
            with PILImage.open(png) as im:
                im.rotate(90, expand=True).save(rotated)
        return image_flowable(rotated, TEXT_W, TEXT_H * 0.88)
    return image_flowable(png, min(TEXT_W, natural_w * 1.15), TEXT_H * 0.72)


# --- Flowables that the contents pages need --------------------------------------------------


class Marker(Flowable):
    """Zero-size flowable recording an entry (heading, figure, table) for the contents."""

    def __init__(self, kind: str, label: str, title: str, level: int = 0, key: str = ""):
        super().__init__()
        self.kind, self.label, self.title, self.level, self.key = kind, label, title, level, key
        self.width = self.height = 0

    def draw(self):
        if self.key:
            self.canv.bookmarkPage(self.key)
            if self.kind == "heading" and self.level <= 3:
                self.canv.addOutlineEntry(
                    f"{self.label} {self.title}".strip(), self.key, level=max(self.level - 1, 0)
                )


class MainStart(Flowable):
    width = height = 0

    def draw(self):
        pass


@dataclass
class Entry:
    kind: str
    label: str
    title: str
    level: int
    page: str


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: str, **kw):
        super().__init__(filename, pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
                         topMargin=TOP, bottomMargin=BOTTOM, title="GoalWise – Project Report",
                         author=kw.pop("author", ""), subject="MCA project report", **kw)
        frame = Frame(LEFT, BOTTOM, TEXT_W, TEXT_H, id="text", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="page", frames=[frame], onPageEnd=self._footer)])
        self.main_start: int | None = None
        self.appendix_start: int | None = None
        self.entries: list[Entry] = []
        self.chapter_pages: dict[str, int] = {}

    def page_label(self, page: int) -> str:
        if self.main_start is None or page < self.main_start:
            return _roman(page)
        return str(page - self.main_start + 1)

    def _footer(self, canvas, doc):
        if doc.page == 1:
            return  # title page: counted, not numbered
        canvas.saveState()
        canvas.setFont("Body", 11)
        canvas.drawCentredString(PAGE_W / 2, 0.55 * inch, self.page_label(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, MainStart):
            self.main_start = self.page
        elif isinstance(flowable, Marker):
            if flowable.kind == "appendix" and self.appendix_start is None:
                self.appendix_start = self.page
            self.entries.append(Entry(flowable.kind, flowable.label, flowable.title,
                                      flowable.level, self.page_label(self.page)))
            if flowable.kind == "heading" and flowable.level == 1:
                self.chapter_pages[f"{flowable.label} {flowable.title}"] = self.page


def _roman(n: int) -> str:
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


# --- Building the story ----------------------------------------------------------------------


@dataclass
class Counters:
    prefix: str = ""  # chapter number or appendix letter
    section: int = 0
    subsection: int = 0
    figure: int = 0
    table: int = 0
    last_heading: str = ""
    section_title: str = ""

    def default_caption(self) -> str:
        """A figure or table without a caption is named after where it stands."""
        if self.section_title and self.last_heading != self.section_title:
            return f"{self.section_title} – {self.last_heading}"
        return self.last_heading


def details() -> dict:
    data = json.loads((HERE / "details.json").read_text(encoding="utf-8"))
    return {k: (v if v else "_" * 22) for k, v in data.items()}


def image_flowable(path: Path, max_w: float, max_h: float) -> Image:
    with PILImage.open(path) as im:
        w_px, h_px = im.size
    scale = min(max_w / w_px, max_h / h_px)
    return Image(str(path), width=w_px * scale, height=h_px * scale)


def table_flowable(rows: list[list[str]], counters: Counters) -> Table:
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    many = ncols >= 5 or sum(len(c) for r in rows for c in r) / max(len(rows), 1) > 260
    cs, hs = (small_cell, small_head) if many else (cell, cell_head)
    # Column widths from the text length, within limits.
    lengths = []
    for c in range(ncols):
        longest = max(len(plain(r[c])) for r in rows)
        average = sum(len(plain(r[c])) for r in rows) / len(rows)
        lengths.append(max(6, min(60, 0.6 * longest + 0.4 * average)))
    total = sum(lengths)
    widths = [TEXT_W * n / total for n in lengths]
    # The longest word that cannot break (code names especially) sets each column's minimum.
    size = cs.fontSize
    floors = []
    for c in range(ncols):
        longest = 0.0
        for r in rows:
            for token in re.findall(r"`[^`]+`|\S+", r[c]):
                if token.startswith("`"):
                    longest = max(longest, (len(token) - 2) * size * 0.6)
                else:
                    longest = max(longest, len(plain(token)) * size * 0.5)
        floors.append(min(max(longest + 10, 0.5 * inch), TEXT_W * 0.42))
    if sum(floors) < TEXT_W:
        for _ in range(4):  # raise columns to their floor, taking the width from the others
            short = [i for i in range(ncols) if widths[i] < floors[i]]
            if not short:
                break
            need = sum(floors[i] - widths[i] for i in short)
            spare = [i for i in range(ncols) if i not in short]
            spare_total = sum(widths[i] - floors[i] for i in spare)
            if spare_total <= 0:
                break
            for i in short:
                widths[i] = floors[i]
            for i in spare:
                widths[i] -= need * (widths[i] - floors[i]) / spare_total
    data = [[P(inline(c) or "&nbsp;", hs if r == 0 else cs) for c in row]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8a8a8a")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def code_flowable(text: str) -> Table:
    width_chars = int(TEXT_W / (code_style.fontSize * 0.6)) - 2
    wrapped = []
    for line in text.expandtabs(4).split("\n"):
        while len(line) > width_chars:
            wrapped.append(line[:width_chars])
            line = "    " + line[width_chars:]
        wrapped.append(line)
    pre = XPreformatted(_fallback(_escape("\n".join(wrapped)), _MONO_CMAP), code_style)
    box = Table([[pre]], colWidths=[TEXT_W])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f3f3")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b0b0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return box


def list_flowable(items: list) -> ListFlowable:
    def build(start: int, depth: int) -> tuple[ListFlowable, int]:
        ordered = items[start][1]
        children = []
        i = start
        while i < len(items) and items[i][0] >= depth:
            if items[i][0] > depth:
                sub, i = build(i, items[i][0])
                children.append(ListItem(sub))
                continue
            children.append(ListItem(P(inline(items[i][2]), list_text), leftIndent=18))
            i += 1
        lf = ListFlowable(
            children,
            bulletType="1" if ordered else "bullet",
            bulletFormat="%s." if ordered else None,
            start=None if ordered else "\u2022",
            bulletFontName="Body",
            bulletFontSize=11,
            leftIndent=18 + 0 * depth,
            bulletDedent=14,
        )
        return lf, i

    lf, _ = build(0, items[0][0])
    return lf


def story_for(blocks: list[Block], counters: Counters, appendix: bool) -> list:
    story: list = []
    for idx, b in enumerate(blocks):
        if b.kind == "pagebreak":
            story.append(PageBreak())
        elif b.kind == "heading":
            title = plain(b.text)
            counters.last_heading = title
            if b.level == 1:
                continue  # chapter titles are set by build_chapter
            if b.level == 2:
                counters.section_title = title
                counters.section += 1
                counters.subsection = 0
                label = f"{counters.prefix}.{counters.section}"
                key = f"h{counters.prefix}_{counters.section}"
                story += [CondPageBreak(1.6 * inch), Marker("heading", label, title, 2, key),
                          P(f"{label}&nbsp;&nbsp;{inline(b.text)}", h2)]
            elif b.level == 3:
                counters.subsection += 1
                label = f"{counters.prefix}.{counters.section}.{counters.subsection}"
                key = f"h{label.replace('.', '_')}"
                story += [CondPageBreak(1.2 * inch), Marker("heading", label, title, 3, key),
                          P(f"{label}&nbsp;&nbsp;{inline(b.text)}", h3)]
            else:
                story += [CondPageBreak(0.9 * inch), P(inline(b.text), h4)]
        elif b.kind == "para":
            # Justified lines stretch badly around long code names: set those flush left.
            long_code = re.search(r"`[^`]{24,}`", b.text)
            story.append(P(inline(b.text), body_left if long_code else body))
        elif b.kind == "display":
            for part in re.split(r"\s{2,}", b.text):
                story.append(P(inline(part), display))
        elif b.kind == "quote":
            story.append(P(inline(b.text), quote))
        elif b.kind == "list":
            story.append(list_flowable(b.items))
            story.append(Spacer(1, 6))
        elif b.kind == "table":
            counters.table += 1
            label = f"Table {counters.prefix}.{counters.table}"
            title = plain(b.caption) or counters.default_caption()
            text = inline(b.caption) if b.caption else _escape(title)
            story += [CondPageBreak(1.4 * inch), Marker("table", label, title),
                      P(f"{label}: {text}", caption), table_flowable(b.items, counters),
                      Spacer(1, 10)]
        elif b.kind == "code":
            story += [code_flowable(b.text), Spacer(1, 8)]
        elif b.kind == "latex":
            png = ASSETS / f"{asset_id('latex', b.text)}.png"
            if png.exists():
                with PILImage.open(png) as im:
                    w, h = im.size
                pt = 0.3  # 2.5 device pixels per CSS pixel, 0.75 pt per CSS pixel
                w_pt, h_pt = w * pt, h * pt
                if w_pt > TEXT_W:
                    h_pt, w_pt = h_pt * TEXT_W / w_pt, TEXT_W
                story += [Image(str(png), width=w_pt, height=h_pt), Spacer(1, 4)]
            else:
                story.append(code_flowable(b.text))
        elif b.kind in ("mermaid", "image", "imagegrid"):
            counters.figure += 1
            label = f"Figure {counters.prefix}.{counters.figure}"
            title = plain(b.caption) or counters.default_caption()
            if b.kind == "mermaid":
                png = diagram_png(b.text)
                if png is None:
                    story.append(code_flowable(b.text))
                    continue
                content = [fitted_diagram(png)]
            elif b.kind == "image":
                path = Path(b.text) if Path(b.text).is_absolute() else (b.base / b.text)
                content = [image_flowable(path.resolve(), TEXT_W, TEXT_H * 0.6)]
            else:
                paths = []
                for cell_text in b.items:
                    m = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", cell_text)
                    p = Path(m.group(2))
                    paths.append(p if p.is_absolute() else (b.base / p).resolve())
                per_row = 2
                gap = 10
                cw = (TEXT_W - gap) / per_row
                cells = [image_flowable(p, cw - 4, TEXT_H * 0.36) for p in paths]
                rows = [cells[k:k + per_row] for k in range(0, len(cells), per_row)]
                rows[-1] += [""] * (per_row - len(rows[-1]))
                grid = Table(rows, colWidths=[cw + gap / 2] * per_row)
                grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                          ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                content = [grid]
            cap = P(f"{label}: {inline(b.caption) if b.caption else _escape(title)}",
                            caption)
            story.append(KeepTogether([Spacer(1, 6), *content, Marker("figure", label, title),
                                       cap]))
    return story


def fill(text: str) -> str:
    """{{field}} placeholders from details.json (blank fields become lines to fill by hand)."""
    d = details()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: d.get(m.group(1), m.group(0)), text)


def build_chapter(path: Path, number: int | str, appendix: bool) -> list:
    text = fill(path.read_text(encoding="utf-8"))
    blocks = parse(text, path.parent)
    title_block = next(b for b in blocks if b.kind == "heading" and b.level == 1)
    title = plain(title_block.text)
    counters = Counters(prefix=str(number))
    story: list = [PageBreak()]
    if number == 1 and not appendix:
        story.append(MainStart())
    if path.stem.startswith("R"):  # references: part of the main text, not numbered
        story += [Marker("front", "", title, 1, "references"),
                  Paragraph(_escape(title).upper(), h_chapter)]
        return story + story_for(blocks, counters, appendix), blocks
    head = f"APPENDIX {number}" if appendix else f"CHAPTER {number}"
    kind = "appendix" if appendix else "heading"
    story += [Marker(kind, head.title() if appendix else str(number), title, 1,
                     f"ch_{number}"),
              Paragraph(head, h_chapter_no), Paragraph(_escape(title).upper(), h_chapter)]
    story += story_for(blocks, counters, appendix)
    return story, blocks


def front_matter(d: dict, entries: list[Entry] | None) -> list:
    """Title page, certificate, declaration, then the chapters' 00-* pages and the contents."""
    s: list = []
    # Title page
    s += [Spacer(1, 0.4 * inch),
          Paragraph("A PROJECT REPORT ON", ParagraphStyle("t0", parent=center, fontName="Body-Bold",
                                                           fontSize=13)),
          Spacer(1, 10),
          Paragraph("GOALWISE: AN ML-DRIVEN GOAL-BASED INVESTMENT AND RETIREMENT PLANNING "
                    "SYSTEM WITH A CONVERSATIONAL AI ASSISTANT",
                    ParagraphStyle("t1", parent=center, fontName="Body-Bold", fontSize=17,
                                   leading=26)),
          Spacer(1, 18),
          Paragraph("Submitted in partial fulfilment of the requirements for the award of the "
                    "degree of", center),
          Paragraph("<b>MASTER OF COMPUTER APPLICATIONS (MCA)</b>", center),
          Spacer(1, 14),
          Paragraph("Submitted by", center),
          Paragraph(f"<b>{_escape(d['learner_name'])}</b>", center),
          Paragraph(f"Enrollment No.: {_escape(d['enrollment_no'])}", center),
          Spacer(1, 14),
          Paragraph("Under the guidance of", center),
          Paragraph(f"<b>{_escape(d['guide_name'])}</b>", center),
          Paragraph(_escape(d["guide_designation"]), center),
          Spacer(1, 24),
          Paragraph("<b>CENTRE FOR DISTANCE AND ONLINE EDUCATION</b>", center),
          Paragraph("<b>ANDHRA UNIVERSITY</b>", center),
          Paragraph("VISAKHAPATNAM – 530 003", center),
          Paragraph(_escape(d["submission_month"]), center),
          PageBreak()]
    # Certificate from the guide (Annexure A of the guidelines)
    s += [Marker("front", "", "Certificate", 1, "front_certificate"),
          Paragraph("CERTIFICATE", h_chapter),
          Paragraph("(To be reproduced on the official letterhead of the guide's institution)",
                    ParagraphStyle("note", parent=center, fontName="Body-Italic", fontSize=11)),
          Spacer(1, 18),
          Paragraph(
              "This is to certify that this project entitled <b>“GoalWise: An ML-Driven "
              "Goal-Based Investment and Retirement Planning System with a Conversational AI "
              "Assistant”</b> submitted in partial fulfilment of the degree of MASTER OF "
              "COMPUTER APPLICATIONS (MCA) to the Andhra University, done by "
              f"Mr./Ms. <b>{_escape(d['learner_name'])}</b>, Roll No. "
              f"<b>{_escape(d['enrollment_no'])}</b>, is authentic work carried out by "
              "him/her under my guidance. The matter embodied in this project's work has not "
              "been submitted earlier for the award of any degree or diploma to the best of "
              "my knowledge and belief.", body),
          Spacer(1, 60),
          Table([[Paragraph("Signature of the student", body_left),
                  Paragraph("Signature of the Guide", body_left)],
                 [Paragraph(_escape(d["learner_name"]), body_left),
                  Paragraph(f"{_escape(d['guide_name'])}<br/>{_escape(d['guide_designation'])}",
                            body_left)]],
                colWidths=[TEXT_W / 2, TEXT_W / 2]),
          PageBreak()]
    # Declaration of originality
    s += [Marker("front", "", "Declaration", 1, "front_declaration"),
          Paragraph("DECLARATION", h_chapter),
          Paragraph(
              f"I, <b>{_escape(d['learner_name'])}</b>, Enrollment No. "
              f"<b>{_escape(d['enrollment_no'])}</b>, hereby declare that the project report "
              "entitled <b>“GoalWise: An ML-Driven Goal-Based Investment and Retirement "
              "Planning System with a Conversational AI Assistant”</b>, submitted to the "
              "Centre for Distance and Online Education, Andhra University, in partial "
              "fulfilment of the requirements for the degree of Master of Computer "
              "Applications, is an original work carried out by me under the guidance of "
              f"<b>{_escape(d['guide_name'])}</b>.", body),
          Paragraph(
              "The design, the source code, the experiments and the results reported here are "
              "my own work. Published methods, libraries, data sources and documentation that "
              "the work builds on are acknowledged in the text and in the references. This "
              "report has not been submitted, in full or in part, to any other university or "
              "institution for the award of any degree or diploma.", body),
          Spacer(1, 48),
          Table([[Paragraph("Place: Visakhapatnam", body_left),
                  Paragraph("Signature of the learner", body_left)],
                 [Paragraph("Date:", body_left),
                  Paragraph(_escape(d["learner_name"]), body_left)]],
                colWidths=[TEXT_W / 2, TEXT_W / 2]),
          ]
    def page(path: Path) -> list:
        blocks = parse(fill(path.read_text(encoding="utf-8")), path.parent)
        title = next(b for b in blocks if b.kind == "heading" and b.level == 1).text
        out = [PageBreak(), Marker("front", "", plain(title), 1, f"front_{path.stem}"),
               Paragraph(_escape(plain(title)).upper(), h_chapter)]
        return out + story_for([b for b in blocks if not (b.kind == "heading" and b.level == 1)],
                               Counters(prefix="0"), False)

    pages = sorted((HERE / "chapters").glob("00-*.md"))
    for path in pages:  # acknowledgement, abstract
        if not path.name.startswith("00-9"):
            s += page(path)
    s += contents_pages(entries)  # contents, figures, tables
    for path in pages:  # abbreviations
        if path.name.startswith("00-9"):
            s += page(path)
    return s


def _dots(title: str, page: str, style: ParagraphStyle, width: float) -> Table:
    t = Table([[Paragraph(title, style), Paragraph(page, ParagraphStyle(
        "pg", parent=style, alignment=2, leftIndent=0))]], colWidths=[width - 40, 40])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def contents_pages(entries: list[Entry] | None) -> list:
    s: list = [PageBreak(), Paragraph("TABLE OF CONTENTS", h_chapter)]
    entries = entries or []
    for e in entries:
        if e.kind == "front" and e.title not in ("Table of Contents",):
            s.append(_dots(_escape(e.title), e.page, toc_1, TEXT_W))
        elif e.kind in ("heading", "appendix"):
            if e.level == 1:
                prefix = f"Chapter {e.label}: " if e.kind == "heading" else f"{e.label}: "
                s += [Spacer(1, 3), _dots(f"{prefix}{_escape(e.title)}", e.page, toc_1, TEXT_W)]
            elif e.level == 2:
                s.append(_dots(f"{e.label}&nbsp;&nbsp;{_escape(e.title)}", e.page, toc_2, TEXT_W))
            elif e.level == 3 and e.kind == "heading":
                s.append(_dots(f"{e.label}&nbsp;&nbsp;{_escape(e.title)}", e.page, toc_3, TEXT_W))
    figs = [e for e in entries if e.kind == "figure"]
    tabs = [e for e in entries if e.kind == "table"]
    s += [PageBreak(), Paragraph("LIST OF FIGURES", h_chapter)]
    s += [_dots(f"{e.label}: {_escape(e.title)}", e.page, toc_2, TEXT_W) for e in figs]
    s += [PageBreak(), Paragraph("LIST OF TABLES", h_chapter)]
    s += [_dots(f"{e.label}: {_escape(e.title)}", e.page, toc_2, TEXT_W) for e in tabs]
    return s


def chapter_files() -> tuple[list[Path], list[Path]]:
    files = sorted(p for p in (HERE / "chapters").glob("*.md") if not p.name.startswith("00-"))
    main = [p for p in files if not p.name.startswith("A")]
    appendices = [p for p in files if p.name.startswith("A")]
    return main, appendices


def build(entries: list[Entry] | None, d: dict) -> ReportDoc:
    main, appendices = chapter_files()
    story = front_matter(d, entries)
    all_blocks: list[Block] = []
    body_story: list = []
    for n, path in enumerate(main, start=1):
        part, blocks = build_chapter(path, n, False)
        body_story += part
        all_blocks += blocks
    for k, path in enumerate(appendices):
        part, blocks = build_chapter(path, "ABCDEFGHIJ"[k], True)
        body_story += part
        all_blocks += blocks
    if entries is None:
        render_assets(all_blocks)
        # Rebuild the chapters so the freshly rendered images are used.
        body_story = []
        for n, path in enumerate(main, start=1):
            body_story += build_chapter(path, n, False)[0]
        for k, path in enumerate(appendices):
            body_story += build_chapter(path, "ABCDEFGHIJ"[k], True)[0]
    doc = ReportDoc(str(OUTPUT), author=d["learner_name"].strip("_") or "")
    doc.build(story + body_story)
    return doc


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    d = details()
    # Pass 1 renders the figures and finds every entry; later passes fill in the contents
    # pages, which moves everything after them, until the page numbers stop changing.
    doc = build(None, d)
    for _ in range(4):
        previous = [(e.label, e.page) for e in doc.entries]
        doc = build(doc.entries, d)
        if [(e.label, e.page) for e in doc.entries] == previous:
            break
    second = doc
    pages = second.page
    main_pages = (second.appendix_start or pages + 1) - (second.main_start or 1)
    print(f"\n{OUTPUT.name}: {pages} pages; main text (chapters + references) = {main_pages} "
          f"pages; front matter = {(second.main_start or 1) - 1} pages")
    starts = sorted(second.chapter_pages.items(), key=lambda kv: kv[1])
    ends = [p for _, p in starts[1:]] + [second.appendix_start or pages + 1]
    for (name, start), end in zip(starts, ends, strict=True):
        print(f"  {end - start:4d}  {name}")


if __name__ == "__main__":
    main()
