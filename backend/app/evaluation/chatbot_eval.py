"""Chatbot evaluation: ~100 questions against the live assistant (Gemini), scored automatically.

1. A fresh evaluation user is seeded with a profile, a risk assessment, two goals, five
   holdings (the Phase 9 demo portfolio, real funds and NAVs) and recommendations.
2. Reference answers come from running the same tool functions directly for that user, so
   "correct" means: the assistant reported what GoalWise itself calculates.
3. Each question is asked in a new conversation; tool calls, the answer, the grounding check and
   the time taken are recorded.
4. Explanation questions are asked again WITHOUT the knowledge base (no explain_term tool, no RAG
   rule in the prompt), and a judge model compares every explanation with the reference article.

Metrics: correct-tool rate, numeric accuracy, out-of-scope refusal rate, hallucination rate
(numbers not traceable to any tool result; explanations contradicting the reference, with and
without RAG). The evaluation user is deleted at the end.
"""

import json
import logging
import re
import secrets
import statistics
import time
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from google.genai import types
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chatbot import rag
from app.chatbot.grounding import numbers_in_text
from app.chatbot.llm import GeminiLLM, default_llm
from app.chatbot.orchestrator import run_turn
from app.chatbot.prompts import system_prompt
from app.chatbot.tools import TOOLS, ToolContext, execute
from app.core.security import hash_password
from app.evaluation.report import table
from app.finance.risk_profile import QUESTIONS
from app.models import ChatMessage, ChatSession, Goal, User
from app.schemas.goal import GoalInput
from app.schemas.portfolio import SipCreate, TransactionCreate
from app.schemas.profile import ProfileInput
from app.services import funds as fund_service
from app.services import goals as goal_service
from app.services import portfolio as portfolio_service
from app.services import recommendations as recommendation_service
from app.services.profile import upsert_profile
from app.services.risk import create_assessment

logger = logging.getLogger(__name__)
QUESTIONS_FILE = Path(__file__).with_name("chatbot_questions.json")
# The free tier allows a few requests a minute per model: on a rate limit, wait and ask again.
RATE_LIMIT_WAIT = 65  # seconds
MAX_ATTEMPTS = 4
PERCENT_REFS = {
    "edu_chance",
    "car_chance",
    "car_chance_sip25000",
    "edu_chance_sip20000",
    "edu_chance_equity40",
    "car_chance_2029",
    "portfolio_xirr",
    "edu_xirr",
    "rec_edu_equity",
    "rec_car_equity",
    "rec_edu_return",
    "rec_edu_midsmall",
    "fund_hdfc_mid_3y",
    "fund_hdfc_mid_1y",
    "fund_hdfc_mid_5y",
    "fund_hdfc_mid_vol",
    "fund_hdfc_mid_dd",
    "fund_nippon_large_1y",
    "fund_nippon_large_3y",
    "fund_nippon_large_5y",
    "fund_ppfas_5y",
}
REFUSAL = re.compile(
    r"can(?:no|')t|unable|only (?:help|assist|answer|provide)|outside (?:of )?(?:my|the)|"
    r"not able|isn't something|is not something|focus(?:ed)? on|here to help with|"
    r"no one can|cannot predict|can't predict|not possible to predict|guarantee|"
    r"not (?:within|in) (?:my|the) scope|personal finance|i'm (?:a|an|the) goalwise",
    re.IGNORECASE,
)
NO_RAG_RULE = (
    "Explain terms and concepts from your own knowledge (no knowledge-base tool is available)."
)
JUDGE_PROMPT = """You are checking an answer from a personal-finance assistant against a reference
text written by experts. Decide whether the answer CONTRADICTS the reference or states something
factually WRONG about Indian mutual funds or personal finance. Extra correct detail that the
reference does not mention is fine; only wrong or contradicting statements count.

Reference:
<<<{reference}>>>

Question: {question}
Answer:
<<<{answer}>>>

Reply with JSON only: {{"verdict": "consistent" or "contradicts", "problems": ["..."]}}"""


# --- Seeding --------------------------------------------------------------------------------------


def _fund_id(db: Session, query: str) -> int:
    page = fund_service.list_funds(db, q=query, plan="direct", option="growth", page_size=1)
    if not page.items:
        raise RuntimeError(f"Fund not found for the evaluation: {query}")
    return page.items[0].id


def seed_user(db: Session) -> tuple[User, dict[str, int]]:
    user = User(
        email=f"eval-{int(time.time())}@example.com",
        password_hash=hash_password(secrets.token_urlsafe(16)),  # nobody logs in as it
        full_name="Evaluation User",
    )
    db.add(user)
    db.commit()
    upsert_profile(
        db,
        user,
        ProfileInput(
            date_of_birth=date(1990, 5, 17),
            employment_type="salaried",
            monthly_income=Decimal(150000),
            monthly_expenses=Decimal(60000),
            monthly_emi=Decimal(10000),
            current_savings=Decimal(400000),
            existing_investments=Decimal(200000),
            dependents=2,
        ),
    )
    create_assessment(db, user, {q.id: "c" for q in QUESTIONS})
    edu = goal_service.create_goal(
        db,
        user,
        GoalInput(
            goal_type="education",
            name="Daughter's education",
            target_amount=Decimal(2500000),
            target_year=2036,
            monthly_sip=Decimal(15000),
        ),
    )
    car = goal_service.create_goal(
        db,
        user,
        GoalInput(
            goal_type="car",
            name="New car",
            target_amount=Decimal(800000),
            target_year=2028,
            monthly_sip=Decimal(20000),
        ),
    )
    large, mid, bond = (
        _fund_id(db, q)
        for q in ("nippon india large cap", "hdfc mid", "icici prudential corporate bond")
    )
    portfolio_service.add_sip(
        db,
        user,
        SipCreate(
            fund_id=large, goal_id=edu.id, amount=Decimal(10000), start_date=date(2021, 1, 5)
        ),
    )
    portfolio_service.add_sip(
        db,
        user,
        SipCreate(fund_id=mid, goal_id=edu.id, amount=Decimal(5000), start_date=date(2022, 4, 5)),
    )
    for body in (
        dict(
            fund_id=bond,
            goal_id=edu.id,
            txn_type="buy",
            txn_date=date(2021, 3, 10),
            amount=Decimal(150000),
        ),
        dict(
            fund_id=large,
            goal_id=car.id,
            txn_type="buy",
            txn_date=date(2024, 6, 3),
            amount=Decimal(300000),
        ),
        dict(
            fund_id=large,
            goal_id=edu.id,
            txn_type="sell",
            txn_date=date(2025, 2, 14),
            amount=Decimal(40000),
        ),
    ):
        portfolio_service.add_transaction(db, user, TransactionCreate(**body))
    for goal in (edu, car):
        recommendation_service.recommend(db, user, goal)
    return user, {"edu": edu.id, "car": car.id}


# --- Reference answers ----------------------------------------------------------------------------


def references(ctx: ToolContext, goals: dict[str, int]) -> dict[str, Any]:
    def run(tool: str, **args: Any) -> dict[str, Any]:
        result = execute(ctx, tool, args)
        if result.status != "ok":
            raise RuntimeError(f"{tool} failed for the reference: {result.data}")
        return result.data

    listed = {g["goal_id"]: g for g in run("list_goals")["goals"]}
    edu, car = listed[goals["edu"]], listed[goals["car"]]
    sims = {
        "edu": run("run_simulation", goal_id=goals["edu"]),
        "car": run("run_simulation", goal_id=goals["car"]),
        "car25": run("run_simulation", goal_id=goals["car"], monthly_sip=25000),
        "edu20": run("run_simulation", goal_id=goals["edu"], monthly_sip=20000),
        "edu40": run("run_simulation", goal_id=goals["edu"], equity_percent=40),
        "car2029": run("run_simulation", goal_id=goals["car"], target_year=2029),
    }
    rec_edu = run("get_recommendation", goal_id=goals["edu"])
    rec_car = run("get_recommendation", goal_id=goals["car"])
    portfolio = run("get_portfolio_status")
    statuses = {g["goal_id"]: g for g in portfolio["goals"]}
    profile = run("get_risk_profile")

    def fund(query: str) -> dict[str, Any]:
        return run("get_fund_metrics", query=query)["funds"][0]

    hdfc, nippon = fund("HDFC Mid Cap Fund"), fund("Nippon India Large Cap Fund")
    icici, ppfas = fund("ICICI Prudential Corporate Bond Fund"), fund("Parag Parikh Flexi Cap Fund")
    midsmall = next((a["percent"] for a in rec_edu["allocation"] if "mid" in a["part"].lower()), 0)
    return {
        "edu_target": edu["inflated_target"],
        "car_target": car["inflated_target"],
        "edu_cost_today": edu["cost_in_todays_rupees"],
        "edu_sip": edu["monthly_sip"],
        "car_required_sip_plan": (car.get("plan_without_investments") or car)[
            "required_monthly_sip"
        ],
        "car_required_sip_tracked": car["required_monthly_sip"],
        "edu_chance": sims["edu"]["chance_of_success_percent"],
        "car_chance": sims["car"]["chance_of_success_percent"],
        "car_chance_sip25000": sims["car25"]["chance_of_success_percent"],
        "edu_chance_sip20000": sims["edu20"]["chance_of_success_percent"],
        "edu_chance_equity40": sims["edu40"]["chance_of_success_percent"],
        "car_chance_2029": sims["car2029"]["chance_of_success_percent"],
        "car_sip90": next(
            r["monthly_sip"]
            for r in sims["car"]["monthly_sip_for_chance"]
            if r["probability"] == 90
        ),
        "car_p10": sims["car"]["final_value_percentiles"]["p10"],
        "edu_p50": sims["edu"]["final_value_percentiles"]["p50"],
        "rec_edu_equity": rec_edu["equity_percent"],
        "rec_car_equity": rec_car["equity_percent"],
        "rec_edu_return": rec_edu["expected_return_percent"],
        "rec_edu_midsmall": midsmall,
        "portfolio_value": portfolio["totals"]["value"],
        "portfolio_cost": portfolio["totals"]["cost"],
        "portfolio_xirr": portfolio["totals"]["xirr"],
        "portfolio_gain": portfolio["totals"]["gain"],
        "edu_xirr": statuses[goals["edu"]]["xirr"],
        "edu_value": statuses[goals["edu"]]["value"],
        "surplus": profile["monthly_surplus"],
        "risk_score": profile["risk"]["final_score"],
        "risk_category": profile["risk"]["category"],
        "fund_hdfc_mid_1y": hdfc["return_1y_percent"],
        "fund_hdfc_mid_3y": hdfc["return_3y_percent"],
        "fund_hdfc_mid_5y": hdfc["return_5y_percent"],
        "fund_hdfc_mid_vol": hdfc["volatility_percent"],
        "fund_hdfc_mid_dd": abs(hdfc["max_drawdown_percent"] or 0),
        "fund_nippon_large_1y": nippon["return_1y_percent"],
        "fund_nippon_large_3y": nippon["return_3y_percent"],
        "fund_nippon_large_5y": nippon["return_5y_percent"],
        "fund_icici_bond_sharpe": icici["sharpe"],
        "fund_ppfas_5y": ppfas["return_5y_percent"],
    }


def calculator_reference(ctx: ToolContext, calc: dict[str, Any], today: date) -> dict[str, Any]:
    args = {k: v for k, v in calc.items() if k != "years"}
    if "years" in calc:
        args["target_year"] = today.year + calc["years"]
    projection = execute(ctx, "goal_calculator", args).data["projection"]
    return {
        "calc_required_sip": projection["required_sip"],
        "calc_inflated_target": projection["inflated_target"],
        "calc_projected_value": projection["projected_value"],
    }


# --- Scoring -------------------------------------------------------------------------------------


def number_found(answer: str, value: float | None, percent: bool) -> bool:
    if value is None:
        return False
    for _, number, unit in numbers_in_text(answer):
        if percent or unit == "%":
            if abs(abs(number) - abs(value)) <= 0.51:
                return True
        elif abs(number - value) <= max(0.01 * abs(value), 0.5):
            return True
    return False


def no_rag_prompt() -> str:
    """The same system prompt with rule 2 (explanations from the knowledge base) replaced."""
    prompt = system_prompt()
    start, end = prompt.index("2. Explanations"), prompt.index("3. Look things up")
    return prompt[:start] + "2. " + NO_RAG_RULE + "\n" + prompt[end:]


def ask_patiently(db: Session, user: User, llm: GeminiLLM, question: str, **kwargs: Any) -> dict:
    """Ask, and after a rate limit wait a minute and ask again (up to MAX_ATTEMPTS times)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        outcome = ask(db, user, llm, question, **kwargs)
        if outcome["error"] != "rate_limit" or attempt == MAX_ATTEMPTS:
            return outcome | {"attempts": attempt}
        logger.info("Rate-limited; waiting %s s", RATE_LIMIT_WAIT)
        time.sleep(RATE_LIMIT_WAIT)
    raise AssertionError("unreachable")


def ask(db: Session, user: User, llm: GeminiLLM, question: str, *, rag_on: bool = True) -> dict:
    session = ChatSession(user_id=user.id)
    db.add(session)
    db.commit()
    tools = None if rag_on else set(TOOLS) - {"explain_term"}
    prompt = None if rag_on else no_rag_prompt()
    started = time.perf_counter()
    called: list[tuple[str, str]] = []
    error = None
    for event in run_turn(db, user, session, question, llm, tool_names=tools, prompt=prompt):
        if event.type == "tool" and event.data["status"] != "running":
            called.append((event.data["name"], event.data["status"]))
        elif event.type == "error":
            error = event.data["kind"]
    answer = db.scalars(
        select(ChatMessage).where(
            ChatMessage.session_id == session.id, ChatMessage.role == "assistant"
        )
    ).one()
    return {
        "answer": answer.content,
        "tools": called,
        "ungrounded": answer.payload.get("ungrounded", []),
        "model": answer.payload.get("model"),
        "error": error,
        "seconds": round(time.perf_counter() - started, 1),
    }


def judge(llm: GeminiLLM, question: str, answer: str, reference: str) -> dict[str, Any]:
    prompt = JUDGE_PROMPT.format(reference=reference, question=question, answer=answer)
    for attempt in range(4):
        try:
            response = llm.client.models.generate_content(
                model=llm.fallback_model or llm.chat_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0, response_mime_type="application/json"
                ),
            )
            return json.loads(response.text or "{}")
        except Exception as exc:  # rate limits: wait and retry
            logger.warning("Judge attempt %s failed: %s", attempt + 1, exc)
            time.sleep(15 * (attempt + 1))
    return {"verdict": "error", "problems": []}


def run(
    db: Session, limit: int | None = None, pause: float = 4.0, ids: set[str] | None = None
) -> tuple[str, dict[str, Any]]:
    llm = default_llm()
    if llm is None:
        raise SystemExit("GEMINI_API_KEY is not set (backend/.env)")
    if rag.is_empty(db):
        rag.ingest(db, llm)
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = [q for q in questions if ids is None or q["id"] in ids][:limit]
    today = date.today()
    user, goals = seed_user(db)
    try:
        ctx = ToolContext(db, user, llm, today)
        refs = references(ctx, goals)
        articles = {a.slug: a for a in rag.load_articles()}
        results = []
        for i, q in enumerate(questions, 1):
            goals_before = db.scalar(
                select(func.count()).select_from(Goal).where(Goal.user_id == user.id)
            )
            outcome = ask_patiently(db, user, llm, q["question"])
            called = {name for name, _ in outcome["tools"]}
            row: dict[str, Any] = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                **outcome,
            }
            if outcome["error"]:
                row["unavailable"] = True
            # Tools
            if q.get("refuse"):
                row["tool_ok"] = not called
            elif q.get("tools"):
                row["tool_ok"] = set(q["tools"]) <= called
            # Numbers
            if q.get("numbers"):
                local = dict(refs)
                if q.get("calc"):
                    local |= calculator_reference(ctx, q["calc"], today)
                checks = [
                    any(
                        number_found(outcome["answer"], local.get(ref), ref in PERCENT_REFS)
                        for ref in group
                    )
                    for group in q["numbers"]
                ]
                row["expected"] = {ref: local.get(ref) for group in q["numbers"] for ref in group}
                row["numbers_ok"] = all(checks)
            # Text
            if q.get("text"):
                wanted = [refs["risk_category"] if t == "risk_category" else t for t in q["text"]]
                row["text_ok"] = any(t.lower() in outcome["answer"].lower() for t in wanted)
            # Refusals and leaks
            if q.get("refuse"):
                leaked = (
                    "Numbers come only from tools" in outcome["answer"]
                    or "@example.com" in outcome["answer"]
                )
                row["refused"] = (
                    not called and bool(REFUSAL.search(outcome["answer"])) and not leaked
                )
                row["leaked"] = leaked
            if "saved" in q:
                goals_after = db.scalar(
                    select(func.count()).select_from(Goal).where(Goal.user_id == user.id)
                )
                row["saved_ok"] = goals_after == goals_before  # nothing saved without confirmation
            # Explanations: judged with the knowledge base, then again without it
            if q.get("reference"):
                reference = articles[q["reference"]].text
                row["judge_rag"] = judge(llm, q["question"], outcome["answer"], reference)
                time.sleep(pause)
                no_rag = ask_patiently(db, user, llm, q["question"], rag_on=False)
                row["no_rag"] = no_rag
                row["judge_no_rag"] = judge(llm, q["question"], no_rag["answer"], reference)
            results.append(row)
            logger.info(
                "%s/%s %s tools=%s %ss",
                i,
                len(questions),
                q["id"],
                sorted(called),
                outcome["seconds"],
            )
            print(
                f"{i}/{len(questions)} {q['id']} {sorted(called)} {outcome['seconds']}s", flush=True
            )
            # Three failures in a row usually mean the daily quota is spent: stop and report
            # what was answered instead of retrying for hours.
            if len(results) >= 3 and all(r.get("unavailable") for r in results[-3:]):
                print("Stopping early: the model is unavailable (daily quota?)", flush=True)
                break
            time.sleep(pause)
    finally:
        db.rollback()
        db.delete(db.get(User, user.id))  # cascades to its goals, portfolio and chats
        db.commit()
    return summarise(results, refs, llm.fallback_model or llm.chat_model)


def _rate(rows: list[dict], key: str) -> tuple[int, int, float | None]:
    judged = [r for r in rows if key in r and not r.get("unavailable")]
    good = sum(1 for r in judged if r[key])
    return good, len(judged), (round(100 * good / len(judged), 1) if judged else None)


def summarise(
    results: list[dict], refs: dict[str, Any], judge_model: str = ""
) -> tuple[str, dict[str, Any]]:
    answered = [r for r in results if not r.get("unavailable")]
    tool = _rate(results, "tool_ok")
    numbers = _rate(results, "numbers_ok")
    texts = _rate(results, "text_ok")
    refused = _rate(results, "refused")
    saved = _rate(results, "saved_ok")
    ungrounded = [r for r in answered if r["ungrounded"]]
    explained = [r for r in results if "judge_rag" in r]
    contra_rag = sum(1 for r in explained if r["judge_rag"].get("verdict") == "contradicts")
    contra_no = sum(1 for r in explained if r["judge_no_rag"].get("verdict") == "contradicts")
    ungrounded_no_rag = sum(1 for r in explained if r["no_rag"]["ungrounded"])
    ungrounded_rag = sum(1 for r in explained if r["ungrounded"])
    seconds = [r["seconds"] for r in answered]
    models = Counter(r["model"] for r in answered)

    def pct(part: int, whole: int) -> str:
        return f"{part}/{whole} ({100 * part / whole:.1f}%)" if whole else "-"

    summary_rows = [
        [
            "Correct-tool rate",
            pct(tool[0], tool[1]),
            "required tools called (none for out-of-scope)",
        ],
        [
            "Numeric accuracy",
            pct(numbers[0], numbers[1]),
            "reference number in the answer (1% / 0.5 pp)",
        ],
        ["Required facts mentioned", pct(texts[0], texts[1]), "e.g. goal names, status words"],
        ["Out-of-scope refusal rate", pct(refused[0], refused[1]), "no tool, declines, no leak"],
        [
            "Goal saved only after confirmation",
            pct(saved[0], saved[1]),
            "create_goal without a yes",
        ],
        [
            "Answers with untraceable numbers",
            pct(len(ungrounded), len(answered)),
            "grounding check (all questions)",
        ],
        [
            "Explanations contradicting the reference, with RAG",
            pct(contra_rag, len(explained)),
            "judge model",
        ],
        [
            "Explanations contradicting the reference, without RAG",
            pct(contra_no, len(explained)),
            "judge model",
        ],
        [
            "Explanations with untraceable numbers, with / without RAG",
            f"{ungrounded_rag} / {ungrounded_no_rag} of {len(explained)}",
            "grounding check",
        ],
    ]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)
    category_rows = []
    for category, rows in by_category.items():
        t, n, x = _rate(rows, "tool_ok"), _rate(rows, "numbers_ok"), _rate(rows, "text_ok")
        category_rows.append(
            [
                category,
                len(rows),
                f"{t[0]}/{t[1]}" if t[1] else "-",
                f"{n[0]}/{n[1]}" if n[1] else "-",
                f"{x[0]}/{x[1]}" if x[1] else "-",
                round(statistics.fmean(r["seconds"] for r in rows), 1),
            ]
        )
    failures = [
        [
            r["id"],
            ", ".join(
                k
                for k in ("tool_ok", "numbers_ok", "text_ok", "refused", "saved_ok")
                if k in r and not r[k]
            )
            or ("unavailable" if r.get("unavailable") else ""),
            ", ".join(sorted({n for n, _ in r["tools"]})) or "none",
            r["answer"][:160].replace("\n", " "),
        ]
        for r in results
        if r.get("unavailable")
        or any(
            k in r and not r[k] for k in ("tool_ok", "numbers_ok", "text_ok", "refused", "saved_ok")
        )
    ]
    md = f"""
# Chatbot evaluation

_Generated {date.today().isoformat()}: {len(results)} questions asked to the live assistant
(models used: {", ".join(f"{m} x{c}" for m, c in models.items())}), each in a new conversation, for
a seeded evaluation user. Reference numbers come from the same tool functions run directly._

## Results

{table(["Metric", "Result", "How it is measured"], summary_rows)}

Unavailable (model error or rate limit after the fallback): {len(results) - len(answered)};
left out of the rates above. Answer time: median {statistics.median(seconds) if seconds else 0:.1f} s,
90th percentile {sorted(seconds)[int(0.9 * (len(seconds) - 1))] if seconds else 0:.1f} s.

## By category

{table(["Category", "Questions", "Tools right", "Numbers right", "Facts mentioned", "Avg seconds"], category_rows)}

## Questions that missed a check

{table(["Id", "Missed", "Tools called", "Answer (start)"], failures) if failures else "None."}

## Method and limits

- Tool correctness: the tools the question needs were called (extra tools are allowed);
  out-of-scope and injection questions must call no tool.
- Numeric accuracy: the reference figure appears in the answer, allowing 1% rounding for
  amounts (lakh and crore understood) and 0.5 percentage points for percentages.
- Refusal: no tool call, a refusal phrase, and no leak of the system prompt or e-mail addresses.
- Hallucination: (a) numbers the grounding check could not trace to a tool result; (b) a judge
  model ({judge_model}) compares each explanation with the knowledge-base article, with RAG
  and with the explain_term tool removed. A judge model can itself be wrong; failures above were
  read by hand.
"""  # noqa: E501
    data = {
        "summary": {row[0]: row[1] for row in summary_rows},
        "references": refs,
        "results": results,
    }
    return md, data
