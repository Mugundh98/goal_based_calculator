"""Writing evaluation results as Markdown tables and JSON."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "evaluation"


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:,.3f}".rstrip("0").rstrip(".") if abs(value) < 10 else f"{value:,.1f}"
        return str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def write(name: str, markdown: str, data: Any, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(
        json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
    )
    path = out_dir / f"{name}.md"
    path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return path
