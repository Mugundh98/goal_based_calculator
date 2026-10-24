"""Joins the report and the source-code appendix into one PDF for submission.

    report/.venv/Scripts/python.exe report/merge_submission.py   (after the two builds)
"""

from pathlib import Path

from pypdf import PdfReader, PdfWriter

BUILD = Path(__file__).resolve().parent / "build"
OUTPUT = BUILD / "GoalWise_Complete_Submission.pdf"

writer = PdfWriter()
for name in ("GoalWise_Project_Report.pdf", "GoalWise_Source_Code.pdf"):
    writer.append(str(BUILD / name))
writer.add_metadata({"/Title": "GoalWise – Project Report with Source Code Appendix"})
writer.write(str(OUTPUT))
print(f"{OUTPUT.name}: {len(PdfReader(str(OUTPUT)).pages)} pages")
