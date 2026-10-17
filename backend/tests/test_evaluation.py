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
