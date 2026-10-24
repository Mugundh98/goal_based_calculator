# Project report

Builds the MCA project report, the source-code appendix and the presentation from the chapters in
`chapters/` and the project's own docs and screenshots. Outputs go to `build/` (not committed).

| Output | What it is |
|---|---|
| `build/GoalWise_Project_Report.pdf` | The report: front matter, Chapters 1–11, references, Appendices A–F |
| `build/GoalWise_Project_Report.docx` | The same report as an editable Word document |
| `build/GoalWise_Source_Code.pdf` | Appendix F: every source file with line numbers |
| `build/GoalWise_Complete_Submission.pdf` | The two above in one file |
| `build/GoalWise_Presentation.pptx` | The viva presentation (20 slides, speaker notes) |

## Before building

Fill in `details.json`: your name, enrolment number, address and mobile, and your guide's name,
designation, address, mobile and experience. Blank fields print as lines to fill by hand.

## Building

One-time setup (from the repository root):

```bash
cd report && npm install && uv venv --python 3.12 .venv && uv pip install --python .venv reportlab pypdf pymupdf pillow python-pptx python-docx pywin32 lxml defusedxml
```

Then, from the repository root:

```bash
report/.venv/Scripts/python.exe report/build_report.py
report/.venv/Scripts/python.exe report/build_docx.py
report/.venv/Scripts/python.exe report/slide_assets.py
node report/build_slides.js
report/.venv/Scripts/python.exe report/build_code_appendix.py
report/.venv/Scripts/python.exe report/merge_submission.py
```

`build_report.py` prints the page count of every chapter. The main text (Chapters 1–11 and the
references) must stay within 150–180 pages. Diagrams and formulas are rendered once, by headless
Chromium through `render_assets.js`, and cached in `build/assets/`.

To check the layout: `preview.py` renders report pages to PNG and `preview_slides.py` draws the
slides and reports text that overflows its box.

## The Word version

`build_docx.py` writes the report as a Word document with the same content, numbering and
figures. Headings use Word's Heading 1–3 styles and captions the Figure Caption and Table Caption
styles, so the table of contents and the lists of figures and tables are Word fields. After
editing, select all (Ctrl+A) and press F9 to refresh their page numbers. If WPS Writer or Word is
installed, the script fills the lists in once and writes `build/GoalWise_Project_Report_docx.pdf`
to check the layout. Edits made in the Word file are not copied back into `chapters/`, so a later
`build_docx.py` run overwrites the file: save your edited copy under another name.

## Not produced here

- The supervisor's certificate must be printed on the guide's letterhead and signed. Page ii is a template for it.
- The guide's bio-data for the proforma (Appendix A).
