"""Writes build/slide_assets.json: the rendered figures the presentation reuses from the report.

    report/.venv/Scripts/python.exe report/slide_assets.py   (after build_report.py)
"""

import json

import build_report as br


def mermaid_in(chapter: str, n: int) -> str:
    path = br.HERE / "chapters" / chapter
    blocks = [b for b in br.parse(br.fill(path.read_text(encoding="utf-8")), path.parent)
              if b.kind == "mermaid"]
    png = br.diagram_png(blocks[n].text)
    return str(png) if png else ""


def latex_in(chapter: str) -> list[str]:
    path = br.HERE / "chapters" / chapter
    blocks = [b for b in br.parse(br.fill(path.read_text(encoding="utf-8")), path.parent)
              if b.kind == "latex"]
    return [str(br.ASSETS / f"{br.asset_id('latex', b.text)}.png") for b in blocks]


assets = {
    "architecture": mermaid_in("06-design.md", 0),
    "workflow": mermaid_in("05-methodology.md", 0),
    "formulas": latex_in("A-2-synopsis.md"),
    "screenshots": str(br.ROOT / "docs" / "screenshots"),
    "details": json.loads((br.HERE / "details.json").read_text(encoding="utf-8")),
}
(br.BUILD / "slide_assets.json").write_text(json.dumps(assets, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in assets.items() if k != "details"}, indent=2))
