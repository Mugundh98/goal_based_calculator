"""Builds the project report as an editable Word document, from the same chapters as the PDF.

    report/.venv/Scripts/python.exe report/build_docx.py   (after build_report.py)

Output: report/build/GoalWise_Project_Report.docx. It reuses build_report.py's parser, numbering
and rendered figures, so the content matches the PDF. Headings use Word's Heading 1–3 styles,
figure and table captions their own styles, so the table of contents and the lists of figures
and tables are real Word fields: after editing, select all and press F9 to refresh them.

If WPS Writer or Microsoft Word is installed, the lists are filled in once here and a PDF of
the Word file is written to build/GoalWise_Project_Report_docx.pdf for checking.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

import build_report as br

OUTPUT = br.BUILD / "GoalWise_Project_Report.docx"
CHECK_PDF = br.BUILD / "GoalWise_Project_Report_docx.pdf"
BODY_FONT, MONO_FONT, SYMBOL_FONT = "Times New Roman", "Courier New", "Segoe UI Symbol"
TITLE = ("GoalWise: An ML-Driven Goal-Based Investment and Retirement Planning System with a "
         "Conversational AI Assistant")

# --- Styles ----------------------------------------------------------------------------------


def set_font(rpr_owner, name: str) -> None:
    """Set all four font slots, dropping theme fonts (which would otherwise win)."""
    rpr = rpr_owner.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn(f"w:{attr}"), None)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), name)


def paragraph_style(doc, name: str, size: float, bold=False, italic=False,
                    align=WD_ALIGN_PARAGRAPH.LEFT, before=0.0, after=0.0, line=None,
                    base="Normal", keep_next=False, indent=0.0):
    styles = doc.styles
    style = styles[name] if name in [s.name for s in styles] else styles.add_style(
        name, WD_STYLE_TYPE.PARAGRAPH)
    if name != "Normal":
        style.base_style = styles[base]
    set_font(style.element, BODY_FONT)
    font = style.font
    font.size, font.bold, font.italic = Pt(size), bold, italic
    color = style.element.get_or_add_rPr().find(qn("w:color"))
    if color is not None:
        style.element.rPr.remove(color)
    font.color.rgb = RGBColor(0, 0, 0)
    pf = style.paragraph_format
    pf.alignment, pf.space_before, pf.space_after = align, Pt(before), Pt(after)
    pf.left_indent = Pt(indent)
    if line == "double":
        pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    elif line is None:
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    else:
        pf.line_spacing = Pt(line)
        pf.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
    pf.keep_with_next = keep_next
    return style


def setup_styles(doc) -> None:
    # Defaults first, so styles we do not touch (lists, tables) are in Times New Roman too.
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    rpr_default = defaults.find(qn("w:rPrDefault")).find(qn("w:rPr"))
    fonts = rpr_default.find(qn("w:rFonts"))
    for attr in list(fonts.attrib):
        del fonts.attrib[attr]
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), BODY_FONT)
    J, C = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER
    paragraph_style(doc, "Normal", 12, align=J, after=6, line="double")
    paragraph_style(doc, "Heading 1", 18, bold=True, align=C, after=24, line=24, keep_next=True)
    paragraph_style(doc, "Heading 2", 14, bold=True, before=14, after=6, line=20, keep_next=True)
    paragraph_style(doc, "Heading 3", 12.5, bold=True, before=10, after=4, line=18,
                    keep_next=True)
    paragraph_style(doc, "Heading 4", 12, bold=True, italic=True, before=6, after=2, line=18,
                    keep_next=True)
    paragraph_style(doc, "Body Left", 12, after=6, line="double")
    paragraph_style(doc, "List Text", 12, line="double")
    paragraph_style(doc, "Quote Text", 12, italic=True, align=J, after=6, line="double",
                    indent=24)
    paragraph_style(doc, "Display", 12, align=C, after=2, line=20)
    paragraph_style(doc, "Front Title", 18, bold=True, align=C, after=24, line=24)
    paragraph_style(doc, "Centered", 12, align=C, line="double")
    paragraph_style(doc, "Figure", 12, align=C, before=6, keep_next=True)
    paragraph_style(doc, "Figure Caption", 11, bold=True, align=C, before=4, after=12)
    paragraph_style(doc, "Table Caption", 11, bold=True, align=C, before=8, after=4,
                    keep_next=True)
    paragraph_style(doc, "Table Text", 10, before=1, after=0.5)
    paragraph_style(doc, "Table Text Small", 9, before=1, after=0.5)
    paragraph_style(doc, "Appendix Heading 3", 12.5, bold=True, before=10, after=4, line=18,
                    keep_next=True)
    code = paragraph_style(doc, "Code", 8.5)
    set_font(code.element, MONO_FONT)
    shade(code.element.get_or_add_pPr(), "F3F3F3")
    borders = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", "4"), ("space", "4"), ("color", "B0B0B0")):
            b.set(qn(f"w:{k}"), v)
        borders.append(b)
    insert_ordered(code.element.get_or_add_pPr(), borders, ("shd",) + AFTER_SHD)
    # Word's own contents styles ("toc 1"...), so a refreshed contents keeps this formatting.
    for level, (size, bold, before, indent) in enumerate(
            ((11.5, True, 3, 0), (11, False, 0, 18), (10.5, False, 0, 40)), start=1):
        style = paragraph_style(doc, f"toc {level}", size, bold=bold, before=before, after=1,
                                indent=indent)
        style.element.attrib.pop(qn("w:customStyle"), None)
        style.element.set(qn("w:styleId"), f"TOC{level}")
        style.paragraph_format.tab_stops.add_tab_stop(
            Pt(br.TEXT_W), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    for name in ("List Bullet", "List Bullet 2", "List Number", "List Number 2"):
        style = doc.styles[name]
        style.base_style = doc.styles["List Text"]
        style.paragraph_format.space_after = Pt(0)


AFTER_SHD = ("tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
             "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
             "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
             "suppressOverlap", "jc", "textDirection", "textAlignment", "textboxTightWrap",
             "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange",
             # table cells
             "noWrap", "tcMar", "tcFitText", "vAlign", "hideMark")


def insert_ordered(parent, element, after_names=AFTER_SHD) -> None:
    """Put a pPr/tcPr child before the first sibling the schema says must follow it."""
    for child in parent:
        if child.tag.split("}")[-1] in after_names:
            child.addprevious(element)
            return
    parent.append(element)


def shade(ppr_or_tcpr, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    insert_ordered(ppr_or_tcpr, shd)


# --- Inline text -----------------------------------------------------------------------------

TAG = re.compile(r"(<[^>]+>)")


def add_inline(par, markdown: str, size: float | None = None) -> None:
    """Markdown inline text as runs, through build_report's markup (same rules as the PDF)."""
    markup = br.inline(markdown)
    bold = italic = sub = sup = False
    fonts: list[str] = []
    for piece in TAG.split(markup):
        if not piece:
            continue
        if piece.startswith("<"):
            tag = piece.lower()
            if tag.startswith("<br"):
                par.add_run().add_break()
            elif tag in ("<b>", "</b>"):
                bold = tag == "<b>"
            elif tag in ("<i>", "</i>"):
                italic = tag == "<i>"
            elif tag in ("<sub>", "</sub>"):
                sub = tag == "<sub>"
            elif tag in ("<super>", "</super>"):
                sup = tag == "<super>"
            elif tag.startswith("<font"):
                fonts.append(MONO_FONT if "mono" in tag else SYMBOL_FONT)
            elif tag == "</font>" and fonts:
                fonts.pop()
            continue
        run = par.add_run(html.unescape(piece))
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if sub:
            run.font.subscript = True
        if sup:
            run.font.superscript = True
        if fonts:
            set_font(run._r, fonts[-1])
            if fonts[-1] == MONO_FONT:
                run.font.size = Pt((size or 12) - 1.5)
        elif size:
            run.font.size = Pt(size)


# --- Document writer -------------------------------------------------------------------------


class Writer:
    def __init__(self, cached: dict[str, list[tuple[str, str]]] | None = None):
        self.cached = cached or {}
        self.appendix = False
        self.doc = Document()
        zoom = self.doc.settings.element.find(qn("w:zoom"))
        if zoom is not None:
            zoom.set(qn("w:percent"), "100")
        setup_styles(self.doc)
        section = self.doc.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.left_margin = Inches(1.5)
        section.right_margin = section.top_margin = section.bottom_margin = Inches(1)
        section.footer_distance = Inches(0.5)
        self.doc._body.clear_content()
        self.break_next = False

    def para(self, style: str, text: str = "", markdown: str | None = None, size=None):
        p = self.doc.add_paragraph(style=style)
        if self.break_next:
            p.paragraph_format.page_break_before = True
            self.break_next = False
        if markdown is not None:
            add_inline(p, markdown, size)
        elif text:
            p.add_run(text)
        return p

    def new_page(self) -> None:
        self.break_next = True

    # Blocks -----------------------------------------------------------------------------

    def heading(self, level: int, label: str, markdown: str) -> None:
        # The PDF's contents list appendix sections but not their subsections.
        appendix_sub = level == 3 and self.appendix
        p = self.para("Appendix Heading 3" if appendix_sub else f"Heading {level}")
        if label:
            p.add_run(f"{label}  ")
        add_inline(p, markdown)

    def chapter_heading(self, head: str, title: str) -> None:
        self.new_page()
        p = self.para("Heading 1")
        if head:
            p.add_run(head + " ").font.size = Pt(16)  # the contents then read "CHAPTER 6 TITLE"
            p.add_run().add_break()
        p.add_run(title.upper())

    def bullet_list(self, items: list) -> None:
        numbering = self.doc.part.numbering_part.element
        fresh: dict[int, int] = {}
        for k, (depth, ordered, text) in enumerate(items):
            depth = min(depth - items[0][0], 1)
            style = ("List Number" if ordered else "List Bullet") + (" 2" if depth else "")
            p = self.para(style, markdown=text)
            if ordered:  # every ordered list restarts at 1
                if depth not in fresh or k == 0:
                    num_id = self.doc.styles[style].element.pPr.numPr.numId.val
                    abstract = numbering.num_having_numId(num_id).abstractNumId.val
                    num = numbering.add_num(abstract)
                    num.add_lvlOverride(ilvl=0).add_startOverride(1)
                    fresh[depth] = num.numId
                p._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = fresh[depth]
            elif depth == 0:
                fresh.clear()
        p.paragraph_format.space_after = Pt(6)

    def table(self, rows: list[list[str]], caption_text: str) -> None:
        self.para("Table Caption", markdown=caption_text)
        ncols = max(len(r) for r in rows)
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        layout = br.table_flowable(rows, br.Counters())  # same column widths as the PDF
        widths = layout._argW
        small = ncols >= 5 or sum(len(c) for r in rows for c in r) / max(len(rows), 1) > 260
        style, size = ("Table Text Small", 9) if small else ("Table Text", 10)
        t = self.doc.add_table(rows=len(rows), cols=ncols)
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                cell = t.cell(r, c)
                cell.width = Pt(widths[c])
                p = cell.paragraphs[0]
                p.style = self.doc.styles[style]
                add_inline(p, text, size)
                if r == 0:
                    for run in p.runs:
                        run.bold = True
                    shade(cell._tc.get_or_add_tcPr(), "E6E6E6")
        header = t.rows[0]._tr.get_or_add_trPr()
        header.append(OxmlElement("w:tblHeader"))
        for c, col in enumerate(t.columns):
            col.width = Pt(widths[c])
        self.para("Table Text").paragraph_format.space_after = Pt(4)

    def code(self, text: str) -> None:
        for line in text.expandtabs(4).split("\n"):
            p = self.para("Code")
            p.add_run(br._fallback(line, br._MONO_CMAP) or " ")
        self.para("Table Text").paragraph_format.space_after = Pt(4)

    def picture(self, path: str, width_pt: float, style: str = "Figure") -> None:
        p = self.para(style)
        p.add_run().add_picture(path, width=Pt(width_pt))

    def image_grid(self, paths: list[Path]) -> None:
        per_row, gap = 2, 10
        cw = (br.TEXT_W - gap) / per_row
        rows = [paths[k:k + per_row] for k in range(0, len(paths), per_row)]
        t = self.doc.add_table(rows=len(rows), cols=per_row)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r, row in enumerate(rows):
            for c, path in enumerate(row):
                img = br.image_flowable(path, cw - 4, br.TEXT_H * 0.36)
                p = t.cell(r, c).paragraphs[0]
                p.style = self.doc.styles["Figure"]
                p.add_run().add_picture(str(path), width=Pt(img.drawWidth))

    def field(self, par, instruction: str, placeholder: str,
              entries: list[tuple[str, str]] | None = None) -> None:
        """A field; with entries, its shown result is those (style, text) lines."""
        def fld(kind: str, target):
            r = OxmlElement("w:r")
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), kind)
            r.append(f)
            target._p.append(r)

        fld("begin", par)
        r = OxmlElement("w:r")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = f" {instruction} "
        r.append(instr)
        par._p.append(r)
        fld("separate", par)
        if not entries:
            par.add_run(placeholder)
            fld("end", par)
            return
        last = par
        for k, (style, text) in enumerate(entries):
            if k:
                last = self.para(style)
            else:
                par.style = self.doc.styles[style]
            last.add_run(text)
        fld("end", last)

    # Chapters ---------------------------------------------------------------------------

    def blocks(self, blocks: list[br.Block], counters: br.Counters) -> None:
        """The Word counterpart of build_report.story_for."""
        for b in blocks:
            if b.kind == "pagebreak":
                self.new_page()
            elif b.kind == "heading":
                title = br.plain(b.text)
                counters.last_heading = title
                if b.level == 1:
                    continue
                if b.level == 2:
                    counters.section_title = title
                    counters.section += 1
                    counters.subsection = 0
                    self.heading(2, f"{counters.prefix}.{counters.section}", b.text)
                elif b.level == 3:
                    counters.subsection += 1
                    self.heading(3, f"{counters.prefix}.{counters.section}."
                                    f"{counters.subsection}", b.text)
                else:
                    self.heading(4, "", b.text)
            elif b.kind == "para":
                long_code = re.search(r"`[^`]{24,}`", b.text)
                self.para("Body Left" if long_code else "Normal", markdown=b.text)
            elif b.kind == "display":
                for part in re.split(r"\s{2,}", b.text):
                    self.para("Display", markdown=part)
            elif b.kind == "quote":
                self.para("Quote Text", markdown=b.text)
            elif b.kind == "list":
                self.bullet_list(b.items)
            elif b.kind == "table":
                counters.table += 1
                label = f"Table {counters.prefix}.{counters.table}"
                title = br.plain(b.caption) or counters.default_caption()
                self.table(b.items, f"{label}: {b.caption or title}")
            elif b.kind == "code":
                self.code(b.text)
            elif b.kind == "latex":
                png = br.ASSETS / f"{br.asset_id('latex', b.text)}.png"
                if not png.exists():
                    self.code(b.text)
                    continue
                from PIL import Image as PILImage
                with PILImage.open(png) as im:
                    w_pt = min(im.size[0] * 0.3, br.TEXT_W)
                self.picture(str(png), w_pt, "Display")
            elif b.kind in br.FIGURES:
                counters.figure += 1
                label = f"Figure {counters.prefix}.{counters.figure}"
                title = br.plain(b.caption) or counters.default_caption()
                if b.kind == "mermaid":
                    png = br.diagram_png(b.text)
                    if png is None:
                        self.code(b.text)
                        continue
                    img = br.fitted_diagram(png)
                    self.picture(img.filename, img.drawWidth)
                elif b.kind == "image":
                    path = Path(b.text) if Path(b.text).is_absolute() else (b.base / b.text)
                    img = br.image_flowable(path.resolve(), br.TEXT_W, br.TEXT_H * 0.6)
                    self.picture(str(path.resolve()), img.drawWidth)
                else:
                    paths = []
                    for cell_text in b.items:
                        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", cell_text)
                        p = Path(m.group(2))
                        paths.append(p if p.is_absolute() else (b.base / p).resolve())
                    self.image_grid(paths)
                self.para("Figure Caption", markdown=f"{label}: {b.caption or title}")

    def chapter(self, path: Path, number: int | str, appendix: bool) -> None:
        blocks = br.parse(br.fill(path.read_text(encoding="utf-8")), path.parent)
        title = br.plain(next(b for b in blocks if b.kind == "heading" and b.level == 1).text)
        self.appendix = appendix
        if path.stem.startswith("R"):
            head = ""
        else:
            head = f"APPENDIX {number}" if appendix else f"CHAPTER {number}"
        if number == 1 and not appendix:  # the main text starts a section numbered from 1
            self.doc.add_section(WD_SECTION.NEW_PAGE)
            self.break_next = False
            p = self.para("Heading 1")
            p.add_run(head + " ").font.size = Pt(16)
            p.add_run().add_break()
            p.add_run(title.upper())
        else:
            self.chapter_heading(head, title)
        self.blocks(blocks, br.Counters(prefix=str(number)))

    def front_page(self, path: Path) -> None:
        blocks = br.parse(br.fill(path.read_text(encoding="utf-8")), path.parent)
        title = br.plain(next(b for b in blocks if b.kind == "heading" and b.level == 1).text)
        self.chapter_heading("", title)
        self.blocks([b for b in blocks if not (b.kind == "heading" and b.level == 1)],
                    br.Counters(prefix="0"))

    def signature_table(self, rows: list[list[str]]) -> None:
        t = self.doc.add_table(rows=len(rows), cols=2)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                p = t.cell(r, c).paragraphs[0]
                p.style = self.doc.styles["Body Left"]
                for k, line in enumerate(text.split("\n")):
                    if k:
                        p.add_run().add_break()
                    p.add_run(line)

    def front_matter(self, d: dict) -> None:
        def centered(text: str = "", bold=False, size=12, before=0):
            p = self.para("Centered")
            p.paragraph_format.space_before = Pt(before)
            if text:
                run = p.add_run(text)
                run.bold, run.font.size = bold, Pt(size)
            return p

        centered("A PROJECT REPORT ON", bold=True, size=13, before=24)
        p = centered(TITLE.upper(), bold=True, size=17, before=10)
        p.paragraph_format.line_spacing = Pt(26)
        centered("Submitted in partial fulfilment of the requirements for the award of the "
                 "degree of", before=18)
        centered("MASTER OF COMPUTER APPLICATIONS (MCA)", bold=True)
        centered("Submitted by", before=14)
        centered(d["learner_name"], bold=True)
        centered(f"Enrollment No.: {d['enrollment_no']}")
        centered("Under the guidance of", before=14)
        centered(d["guide_name"], bold=True)
        centered(d["guide_designation"])
        centered("CENTRE FOR DISTANCE AND ONLINE EDUCATION", bold=True, before=24)
        centered("ANDHRA UNIVERSITY", bold=True)
        centered("VISAKHAPATNAM – 530 003")
        centered(d["submission_month"])

        self.chapter_heading("", "Certificate")
        note = self.para("Centered", "(To be reproduced on the official letterhead of the "
                                     "guide's institution)")
        note.runs[0].italic, note.runs[0].font.size = True, Pt(11)
        p = self.para("Normal")
        p.paragraph_format.space_before = Pt(18)
        for text, bold in (("This is to certify that this project entitled ", False),
                           (f"“{TITLE}”", True),
                           (" submitted in partial fulfilment of the degree of MASTER OF "
                            "COMPUTER APPLICATIONS (MCA) to the Andhra University, done by "
                            "Mr./Ms. ", False), (d["learner_name"], True), (", Roll No. ", False),
                           (d["enrollment_no"], True),
                           (", is authentic work carried out by him/her under my guidance. The "
                            "matter embodied in this project's work has not been submitted "
                            "earlier for the award of any degree or diploma to the best of my "
                            "knowledge and belief.", False)):
            p.add_run(text).bold = bold
        self.para("Normal").paragraph_format.space_before = Pt(36)
        self.signature_table([["Signature of the student", "Signature of the Guide"],
                              [d["learner_name"],
                               f"{d['guide_name']}\n{d['guide_designation']}"]])

        self.chapter_heading("", "Declaration")
        p = self.para("Normal")
        for text, bold in (("I, ", False), (d["learner_name"], True),
                           (", Enrollment No. ", False), (d["enrollment_no"], True),
                           (", hereby declare that the project report entitled ", False),
                           (f"“{TITLE}”", True),
                           (", submitted to the Centre for Distance and Online Education, "
                            "Andhra University, in partial fulfilment of the requirements for "
                            "the degree of Master of Computer Applications, is an original work "
                            "carried out by me under the guidance of ", False),
                           (d["guide_name"], True), (".", False)):
            p.add_run(text).bold = bold
        self.para("Normal", "The design, the source code, the experiments and the results "
                            "reported here are my own work. Published methods, libraries, data "
                            "sources and documentation that the work builds on are acknowledged "
                            "in the text and in the references. This report has not been "
                            "submitted, in full or in part, to any other university or "
                            "institution for the award of any degree or diploma.")
        self.para("Normal").paragraph_format.space_before = Pt(24)
        self.signature_table([["Place: Visakhapatnam", "Signature of the learner"],
                              ["Date:", d["learner_name"]]])

        pages = sorted((br.HERE / "chapters").glob("00-*.md"))
        for path in pages:
            if not path.name.startswith("00-9"):
                self.front_page(path)
        hint = "Right-click here and choose Update Field (or press F9) to build this list."
        for title, instruction in (("TABLE OF CONTENTS", 'TOC \\o "1-3" \\h \\z \\u'),
                                   ("LIST OF FIGURES", 'TOC \\h \\z \\t "Figure Caption,2"'),
                                   ("LIST OF TABLES", 'TOC \\h \\z \\t "Table Caption,2"')):
            self.new_page()
            self.para("Front Title", title)
            self.field(self.para("toc 1"), instruction, hint, self.cached.get(title))
        for path in pages:
            if path.name.startswith("00-9"):
                self.front_page(path)

    # Page numbers -----------------------------------------------------------------------

    def page_numbers(self) -> None:
        front, main = self.doc.sections[0], self.doc.sections[-1]
        for section, fmt in ((front, "lowerRoman"), (main, "decimal")):
            sect = section._sectPr
            pg = sect.find(qn("w:pgNumType"))
            if pg is None:
                pg = OxmlElement("w:pgNumType")
                cols = sect.find(qn("w:cols"))
                if cols is not None:
                    cols.addprevious(pg)
                else:
                    sect.find(qn("w:pgMar")).addnext(pg)
            pg.set(qn("w:fmt"), fmt)
            pg.set(qn("w:start"), "1")
        front.different_first_page_header_footer = True  # title page: counted, not numbered
        p = front.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        simple = OxmlElement("w:fldSimple")
        simple.set(qn("w:instr"), "PAGE")
        run = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "22")
        rpr.append(sz)
        run.append(rpr)
        t = OxmlElement("w:t")
        t.text = "1"
        run.append(t)
        simple.append(run)
        p._p.append(simple)


def build(cached: dict | None = None, output: Path = OUTPUT) -> Path:
    d = br.details()
    w = Writer(cached)
    w.front_matter(d)
    main, appendices = br.chapter_files()
    for n, path in enumerate(main, start=1):
        w.chapter(path, n, False)
    for k, path in enumerate(appendices):
        w.chapter(path, "ABCDEFGHIJ"[k], True)
    w.page_numbers()
    props = w.doc.core_properties
    props.title, props.subject = "GoalWise – Project Report", "MCA project report"
    props.author = d["learner_name"].strip("_")
    w.doc.save(str(output))
    return output


def computed_lists(path: Path) -> dict[str, list[tuple[str, str]]]:
    """The contents lines an office application wrote into the fields, per list title."""
    lists: dict[str, list[tuple[str, str]]] = {}
    current = None
    for p in Document(str(path)).paragraphs:
        name = p.style.name if p.style is not None else ""
        if name == "Front Title":
            current = lists.setdefault(p.text.strip(), [])
        elif name.lower().startswith("toc") and current is not None and p.text.strip():
            current.append((f"toc {name.strip()[-1]}", p.text))
    return lists


def office_app():
    """Word, or WPS Writer (which also answers to Word's name), through COM; None if neither."""
    try:
        import win32com.client
    except ImportError:
        return None
    for prog_id in ("Word.Application", "KWPS.Application"):
        try:
            app = win32com.client.DispatchEx(prog_id)
            app.Visible = False
            return app
        except Exception:
            continue
    return None


def export_pdf(path: Path) -> None:
    app = office_app()
    if app is None:
        return
    try:
        doc = app.Documents.Open(str(path), ReadOnly=True)
        doc.ExportAsFixedFormat(str(CHECK_PDF), 17)
        doc.Close(False)
        print(f"check PDF: {CHECK_PDF.name}")
    finally:
        app.Quit()


def update_fields(path: Path) -> dict | None:
    """Compute the contents lists with Word or WPS Writer (on a copy); write a PDF to check.

    The application's own save is not kept: WPS writes styles in an order that fails Word's
    schema, so the lists it computed are copied into a fresh build instead."""
    app = office_app()
    if app is None:
        print("no Word or WPS found: open the file and press F9 to build the contents")
        return None
    copy = path.with_name("_fields.docx")
    shutil.copy(path, copy)
    try:
        doc = app.Documents.Open(str(copy))
        for _ in range(2):  # the second pass sees the page numbers the first one moved
            for k in range(1, doc.TablesOfContents.Count + 1):
                doc.TablesOfContents(k).Update()
        doc.Save()
        doc.Close(False)
        print(f"contents computed by {app.Name}")
    finally:
        app.Quit()
    lists = computed_lists(copy)
    copy.unlink()
    return lists


if __name__ == "__main__":
    out = build()
    lists = update_fields(out)
    if lists:
        build(lists)
        print(", ".join(f"{k.title()}: {len(v)} lines" for k, v in lists.items()))
        export_pdf(out)
    print(f"wrote {out}")
