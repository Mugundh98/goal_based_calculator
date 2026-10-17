"""Evaluation helpers: SUS scoring, UAT results, number matching and report tables."""

import csv

import pytest

from app.evaluation import uat
from app.evaluation.chatbot_eval import REFUSAL, no_rag_prompt, number_found
from app.evaluation.report import table


def test_sus_score_follows_the_standard_formula():
    assert uat.sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100
    assert uat.sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0
    assert uat.sus_score([3] * 10) == 50
    assert uat.sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75
    with pytest.raises(ValueError):
        uat.sus_score([3] * 9)
    with pytest.raises(ValueError):
        uat.sus_score([6] + [3] * 9)


def test_sus_grades():
    assert [uat.grade(s) for s in (90, 75, 60, 40, 10)] == [
        "Excellent",
        "Good",
        "OK",
        "Poor",
        "Awful",
    ]


def test_uat_results_from_a_responses_file(tmp_path):
    path = tmp_path / "responses.csv"
    header = [
        "participant",
        "profile",
        *uat.TASKS,
        "minutes",
        *uat.SUS_ITEMS,
        *uat.EXTRA,
        "comment",
    ]
    rows = [
        [
            "P1",
            "salaried, 34",
            *["1"] * 8,
            "25",
            *["4", "2"] * 5,
            "5",
            "4",
            "4",
            "5",
            "Clear charts",
        ],
        ["P2", "student, 23", *["1"] * 7, "0.5", "31", *["5", "1"] * 5, "4", "5", "3", "4", ""],
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file).writerows([header, *rows])  # quotes "salaried, 34"
    markdown, data = uat.build(path)
    assert data["participants"] == 2
    assert data["mean_sus"] == 87.5  # (75 + 100) / 2
    assert data["task_rates"][-1] == 75.0  # task 8: one unaided, one with help
    assert "Clear charts" in markdown and "Excellent" in markdown


def test_empty_responses_explain_what_to_do(tmp_path):
    path = tmp_path / "responses.csv"
    path.write_text("participant,profile\n", encoding="utf-8")
    markdown, data = uat.build(path)
    assert data["participants"] == 0 and "No responses yet" in markdown


@pytest.mark.parametrize(
    ("answer", "value", "percent", "found"),
    [
        ("You need ₹29,837 a month.", 29837, False, True),
        ("about ₹1.20 crore", 11_982_791, False, True),  # 0.14% off: rounding is fine
        ("about ₹1.3 crore", 11_982_791, False, False),
        ("a 16.8% chance", 16.8, True, True),
        ("roughly 17%", 16.8, True, True),
        ("a 20% chance", 16.8, True, False),
        ("no numbers here", 5, False, False),
    ],
)
def test_reference_numbers_are_found_with_rounding(answer, value, percent, found):
    assert number_found(answer, value, percent) is found


def test_refusal_phrases_and_the_no_rag_prompt():
    assert REFUSAL.search("I can only help with personal finance and your goals.")
    assert REFUSAL.search("I'm not able to share that.")
    assert not REFUSAL.search("Your SIP of ₹15,000 is on track.")
    prompt = no_rag_prompt()
    assert "explain_term" not in prompt.split("3. Look things up")[0]
    assert "from your own knowledge" in prompt and "3. Look things up" in prompt


def test_markdown_table():
    assert table(["A", "B"], [[1, None], ["x|y", 12.3456]]) == (
        "| A | B |\n|---|---|\n| 1 | - |\n| x\\|y | 12.3 |"
    )


# --- Reports built from the database (no Gemini needed) ---------------------------------------


def _fold(year, model_ic, momentum_ic):
    def scores(ic, hit):
        return {
            "rows": 1000,
            "rank_ic": ic,
            "top_pick_hit_rate": hit,
            "accuracy": 0.35,
            "macro_f1": 0.33,
            "top_pick_median_excess": 0.2,
        }

    return {
        "year": year,
        "model": scores(model_ic, 0.36),
        "momentum": scores(momentum_ic, 0.37),
        "random": scores(0.0, 0.25),
    }


def test_ml_report_compares_the_ranker_with_naive_baselines(db):
    from datetime import date

    from app.evaluation import ml_report
    from app.models import MLModel

    folds = [_fold(2021, 0.30, 0.20), _fold(2022, 0.10, 0.20), _fold(2023, 0.25, 0.25)]
    db.add_all(
        [
            MLModel(
                name="fund_ranker",
                version=1,
                algorithm="LightGBM",
                params={},
                metrics={
                    "reported_years": {"folds": folds, "pooled": folds[0]},
                    "leaky_random_split": {"rank_ic": 0.24},
                },
                data_start=date(2015, 1, 31),
                data_end=date(2025, 12, 31),
                is_active=True,
            ),
            MLModel(
                name="inflation_forecast",
                version=1,
                algorithm="SARIMA",
                params={},
                metrics={
                    "evaluation": {
                        "origins": ["2018-12", "2024-12"],
                        "mae_12m_ahead": {"sarima": 1.31, "naive": 1.74},
                        "mae_by_horizon": {"sarima": [0.5] * 12},
                    }
                },
                data_start=date(2011, 1, 1),
                data_end=date(2025, 12, 1),
                is_active=True,
            ),
        ]
    )
    db.commit()
    markdown, data = ml_report.build(db, date(2026, 10, 18))
    assert data["fund_ranker"]["model_minus_momentum_rank_ic"] == pytest.approx([0.1, -0.1, 0.0])
    assert data["fund_ranker"]["years_model_beats_momentum"] == 1
    assert "Last year's top funds" in markdown and "paired" in markdown
    assert "SARIMA 1.31 pp, naive 1.74 pp" in markdown
    assert "No active model" in markdown  # clusters were not trained here


def test_return_model_report_without_market_data_uses_the_normal_model(db):
    from datetime import date

    from app.evaluation import return_models

    markdown, data = return_models.build(db, date(2026, 10, 18))
    assert len(data["goals"]) == len(return_models.SAMPLES)
    for goal in data["goals"]:
        assert list(goal["models"]) == ["normal"]  # the others need market history
        assert 35 < goal["models"]["normal"]["success"] < 65  # the plan's SIP: about even odds
        assert goal["models"]["normal"]["sip_for_90"] > goal["monthly_sip"]
    assert "Chance of reaching the target" in markdown


def test_chatbot_summary_counts_every_metric():
    from app.evaluation.chatbot_eval import summarise

    def row(i, category, **checks):
        return {
            "id": i,
            "category": category,
            "question": "q",
            "answer": "a",
            "tools": [],
            "ungrounded": [],
            "model": "lite",
            "error": None,
            "seconds": 2.0,
            **checks,
        }

    consistent, contradicts = {"verdict": "consistent"}, {"verdict": "contradicts"}
    no_rag = {"answer": "b", "tools": [], "ungrounded": ["7"], "seconds": 1.0}
    results = [
        row("G1", "goals", tool_ok=True, numbers_ok=True),
        row("G2", "goals", tool_ok=False, numbers_ok=False, ungrounded=["9"]),
        row("O1", "out_of_scope", tool_ok=True, refused=True),
        row(
            "E1",
            "explain",
            tool_ok=True,
            judge_rag=consistent,
            judge_no_rag=contradicts,
            no_rag=no_rag,
        ),
        row("X1", "goals", tool_ok=False, unavailable=True),
    ]
    markdown, data = summarise(results, {}, "judge-model")
    summary = data["summary"]
    assert summary["Correct-tool rate"] == "3/4 (75.0%)"  # the unavailable one is left out
    assert summary["Numeric accuracy"] == "1/2 (50.0%)"
    assert summary["Out-of-scope refusal rate"] == "1/1 (100.0%)"
    assert summary["Answers with untraceable numbers"] == "1/4 (25.0%)"
    assert summary["Explanations contradicting the reference, with RAG"] == "0/1 (0.0%)"
    assert summary["Explanations contradicting the reference, without RAG"] == "1/1 (100.0%)"
    assert "G2" in markdown and "judge-model" in markdown and "Unavailable" in markdown
