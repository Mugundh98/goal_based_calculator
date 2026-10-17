"""User acceptance testing: score the feedback forms and build the results table.

Fill docs/evaluation/uat/responses.csv (one row per participant) after the sessions, then

    uv run python -m app.evaluation uat

The System Usability Scale (SUS, Brooke 1996) has 10 statements answered 1 (strongly disagree)
to 5 (strongly agree). Odd items are positive: score - 1. Even items are negative: 5 - score.
The sum (0-40) times 2.5 gives 0-100; about 68 is average, above 80 is excellent.
"""

import csv
import statistics
from pathlib import Path
from typing import Any

from app.evaluation.report import OUT_DIR, table

RESPONSES = OUT_DIR / "uat" / "responses.csv"
TASKS = [f"task{i}" for i in range(1, 9)]  # 1 = completed unaided, 0.5 = with help, 0 = failed
SUS_ITEMS = [f"sus{i}" for i in range(1, 11)]
EXTRA = ["useful", "trust_numbers", "assistant_helpful", "would_use"]  # 1-5


def sus_score(answers: list[int]) -> float:
    """SUS score 0-100 from the 10 answers (each 1-5) in questionnaire order."""
    if len(answers) != 10 or any(a < 1 or a > 5 for a in answers):
        raise ValueError("SUS needs 10 answers between 1 and 5")
    total = sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))
    return total * 2.5


def grade(score: float) -> str:
    """Adjective scale often used with SUS (Bangor, Kortum & Miller 2009)."""
    for limit, word in ((85.5, "Excellent"), (71.4, "Good"), (51.7, "OK"), (25, "Poor")):
        if score >= limit:
            return word
    return "Awful"


def load(path: Path = RESPONSES) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("participant", "").strip()]


def build(path: Path = RESPONSES) -> tuple[str, dict[str, Any]]:
    rows = load(path)
    if not rows:
        return (
            "# UAT results\n\nNo responses yet: fill docs/evaluation/uat/responses.csv after the "
            "sessions (see docs/evaluation/uat/uat-plan.md).",
            {"participants": 0},
        )
    people = []
    for row in rows:
        sus = sus_score([int(row[i]) for i in SUS_ITEMS])
        people.append(
            {
                "participant": row["participant"],
                "profile": row.get("profile", ""),
                "tasks": [float(row[t]) for t in TASKS],
                "minutes": float(row["minutes"]) if row.get("minutes") else None,
                "sus": sus,
                **{k: int(row[k]) for k in EXTRA if row.get(k)},
                "comment": row.get("comment", ""),
            }
        )
    task_rates = [
        round(100 * statistics.fmean(p["tasks"][i] for p in people), 1) for i in range(len(TASKS))
    ]
    sus_values = [p["sus"] for p in people]
    mean_sus = statistics.fmean(sus_values)
    per_person = [
        [p["participant"], p["profile"], f"{sum(p['tasks']):g}/{len(TASKS)}", p["minutes"],
         p["sus"], *(p.get(k) for k in EXTRA)]
        for p in people
    ]  # fmt: skip
    extras = {k: round(statistics.fmean(p[k] for p in people if k in p), 2) for k in EXTRA}
    md = f"""
# UAT results

{len(people)} participants. Mean SUS **{mean_sus:.1f}** ({grade(mean_sus)}), range
{min(sus_values):g}-{max(sus_values):g}.

## Task completion (% of participants; help counts as half)

{table(["Task", *[f"T{i}" for i in range(1, len(TASKS) + 1)]], [["Completed", *task_rates]])}

## Participants

{
        table(
            [
                "Participant",
                "Profile",
                "Tasks",
                "Minutes",
                "SUS",
                "Useful",
                "Trust numbers",
                "Assistant helpful",
                "Would use",
            ],
            per_person,
        )
    }

## Mean of the GoalWise questions (1-5)

{
        table(
            ["Useful", "Trust the numbers", "Assistant helpful", "Would use it"],
            [[extras.get(k) for k in EXTRA]],
        )
    }

## Comments

{chr(10).join(f"- {p['participant']}: {p['comment']}" for p in people if p["comment"]) or "None."}
"""
    return md, {"participants": len(people), "mean_sus": mean_sus, "task_rates": task_rates,
                "people": people}  # fmt: skip
