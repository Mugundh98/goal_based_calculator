"""The functions the model may call. Each one calls an existing service for the logged-in user.

A tool = name + description + JSON schema of its arguments (generated from a Pydantic model,
which also validates what the model sends) + a Python function. The model never touches the
database or does arithmetic: it chooses a tool, the server runs it with the user's own
permissions, and the model words the result. Results are kept small and free of personal
identifiers (no name, e-mail or date of birth); charts go to the browser, not to the model.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.chatbot import rag
from app.chatbot.llm import LLM, ToolSpec
from app.finance.formatting import inr
from app.models import Goal, User
from app.schemas.goal import GoalCalculationInput, GoalInput
from app.schemas.portfolio import GoalStatus
from app.schemas.simulation import SimulationOverrides, SimulationRequest
from app.services import audit
from app.services import funds as fund_service
from app.services import goals as goal_service
from app.services import portfolio as portfolio_service
from app.services import profile as profile_service
from app.services import recommendations as recommendation_service
from app.services import simulations as simulation_service
from app.services.risk import latest_assessment

logger = logging.getLogger(__name__)

RELEVANT_SIMILARITY = 0.60  # measured: on-topic passages 0.69+, off-topic questions 0.53 or less


class ToolError(Exception):
    """Shown to the model as {"error": ...}; it explains the problem to the user."""


@dataclass
class ToolContext:
    db: Session
    user: User
    llm: LLM
    today: date | None = None
    # Tools that asked the user to confirm in the previous answer (see create_goal).
    awaiting_confirmation: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ToolOutput:
    data: dict[str, Any]  # for the model
    chart: dict[str, Any] | None = None  # for the browser only


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[ToolContext, Any], ToolOutput]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, json_schema(self.args))


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic's schema, simplified for function declarations (no titles, refs or nulls)."""
    raw = model.model_json_schema()
    definitions = raw.pop("$defs", {})

    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return clean(definitions[node["$ref"].split("/")[-1]])
        if "anyOf" in node:  # Optional[X] -> X
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            merged = {k: v for k, v in node.items() if k not in ("anyOf", "default")}
            if len(options) == 1:
                return clean({**options[0], **merged})
        return {k: clean(v) for k, v in node.items() if k != "title"}

    return clean(raw)


def _money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def _owned_goal(ctx: ToolContext, goal_id: int) -> Goal:
    goal = goal_service.get_goal(ctx.db, ctx.user, goal_id)
    if goal is None:
        raise ToolError(f"There is no goal with id {goal_id}. Call list_goals to see the ids.")
    return goal


# --- Goals -----------------------------------------------------------------------------------


class NoArgs(BaseModel):
    pass


def _tracked(ctx: ToolContext) -> dict[int, GoalStatus]:
    """Goals with recorded investments (Phase 9), by id: their status uses the real holdings."""
    statuses = portfolio_service.portfolio(ctx.db, ctx.user, ctx.today).goals
    return {g.goal_id: g for g in statuses if g.status != "not_started"}


def list_goals(ctx: ToolContext, _: NoArgs) -> ToolOutput:
    category = goal_service.risk_category(ctx.db, ctx.user)
    tracked = _tracked(ctx)
    goals = []
    for goal in goal_service.list_goals(ctx.db, ctx.user):
        p = goal_service.calculate(goal, category, ctx.today)
        entry: dict[str, Any] = {
            "goal_id": goal.id,
            "name": goal.name,
            "goal_type": goal.goal_type,
            "target_year": goal.target_year,
            "years_to_goal": p.years_to_goal,
            "cost_in_todays_rupees": float(goal.target_amount),
            "inflation_rate_percent": float(goal.inflation_rate),
            "inflated_target": p.inflated_target,
            "current_savings": float(goal.current_savings),
            "monthly_sip": float(goal.monthly_sip),
            "step_up_rate_percent": float(goal.step_up_rate),
            "expected_return_percent": p.expected_return_used,
            "projected_value": p.projected_value,
            "funded_percent": p.funded_percent,
            "on_track": p.on_track,
            "required_monthly_sip": p.required_sip,
        }
        status = tracked.get(goal.id)
        if status is not None:
            # The plan fields above start from the typed-in savings; these use the holdings.
            entry["recorded_investments"] = status.model_dump(
                include={
                    "status",
                    "value",
                    "cost",
                    "xirr",
                    "plan_value",
                    "vs_plan",
                    "projected_value",
                    "funded_percent",
                    "shortfall",
                    "required_sip",
                    "rebalance_needed",
                }
            )
        goals.append(entry)
    return ToolOutput(
        {
            "risk_category": category,
            "goals": goals,
            "note": "When a goal has recorded_investments, its status there (based on the real "
            "holdings) is the up-to-date answer to whether the goal is on track.",
        }
    )  # fmt: skip


class CalculatorArgs(BaseModel):
    target_amount: float = Field(gt=0, lt=1e10, description="Cost of the goal in today's rupees")
    target_year: int = Field(description="Calendar year the money is needed")
    current_savings: float = Field(default=0, ge=0, description="Rupees already set aside")
    monthly_sip: float = Field(default=0, ge=0, description="Rupees invested each month now")
    inflation_rate: float = Field(default=6, ge=0, le=20, description="Percent a year")
    expected_return: float | None = Field(
        default=None, ge=0, le=30, description="Percent a year; omit to use the risk profile"
    )
    step_up_rate: float = Field(default=0, ge=0, le=50, description="Yearly SIP increase, %")


def _calculation_input(args: CalculatorArgs) -> dict[str, Any]:
    return {
        "target_amount": _money(args.target_amount),
        "target_year": args.target_year,
        "current_savings": _money(args.current_savings),
        "monthly_sip": _money(args.monthly_sip),
        "inflation_rate": _money(args.inflation_rate),
        "expected_return": None if args.expected_return is None else _money(args.expected_return),
        "step_up_rate": _money(args.step_up_rate),
    }


def _projection(ctx: ToolContext, args: CalculatorArgs) -> dict[str, Any]:
    try:
        data = GoalCalculationInput(**_calculation_input(args))
    except ValidationError as error:
        raise ToolError(error.errors()[0]["msg"]) from None
    category = goal_service.risk_category(ctx.db, ctx.user)
    return goal_service.calculate(data, category, ctx.today).model_dump()


def goal_calculator(ctx: ToolContext, args: CalculatorArgs) -> ToolOutput:
    return ToolOutput({"projection": _projection(ctx, args), "saved": False})


class CreateGoalArgs(CalculatorArgs):
    goal_type: Literal[
        "education", "house", "car", "marriage", "travel", "emergency_fund", "wealth", "other"
    ]
    name: str = Field(min_length=1, max_length=100)
    priority: int = Field(default=2, ge=1, le=3, description="1 high, 2 medium, 3 low")
    confirmed: bool = Field(
        default=False,
        description="true only after the user has seen the details and said yes in chat",
    )


def create_goal(ctx: ToolContext, args: CreateGoalArgs) -> ToolOutput:
    projection = _projection(ctx, args)
    # Human in the loop, enforced here and not only in the prompt: a goal is saved only if the
    # previous answer showed a preview and asked for confirmation.
    if not args.confirmed or "create_goal" not in ctx.awaiting_confirmation:
        return ToolOutput(
            {
                "saved": False,
                "needs_confirmation": True,
                "details": args.model_dump(exclude={"confirmed"}),
                "projection": projection,
                "instruction": "Show these details to the user and ask whether to save the "
                "goal. Call create_goal again with confirmed=true only after they agree.",
            }
        )
    data = GoalInput(
        goal_type=args.goal_type,
        name=args.name,
        priority=args.priority,
        **_calculation_input(args),
    )
    goal = goal_service.create_goal(ctx.db, ctx.user, data)
    audit.record(
        ctx.db,
        "assistant.goal.create",
        actor=ctx.user,
        entity_type="goal",
        entity_id=goal.id,
        details={"name": goal.name, "goal_type": goal.goal_type, "target_year": goal.target_year},
    )
    ctx.db.commit()
    return ToolOutput({"saved": True, "goal_id": goal.id, "projection": projection})


# --- Simulation and recommendation --------------------------------------------------------------


class SimulationArgs(BaseModel):
    goal_id: int
    monthly_sip: float | None = Field(default=None, ge=0, description="What-if SIP, rupees")
    equity_percent: float | None = Field(
        default=None, ge=0, le=100, description="What-if share of the money in equity"
    )
    target_year: int | None = Field(default=None, description="What-if target year")
    step_up_rate: float | None = Field(default=None, ge=0, le=50, description="What-if, %")
    current_savings: float | None = Field(
        default=None, ge=0, description="What-if starting amount; omit to use what is invested"
    )


def run_simulation(ctx: ToolContext, args: SimulationArgs) -> ToolOutput:
    goal = _owned_goal(ctx, args.goal_id)
    start = args.current_savings
    start_source = "what-if" if start is not None else "goal's current savings"
    if start is None and (status := _tracked(ctx).get(goal.id)) is not None:
        start, start_source = status.value, "recorded investments (portfolio)"
    try:
        overrides = SimulationOverrides(
            current_savings=None if start is None else _money(start),
            monthly_sip=None if args.monthly_sip is None else _money(args.monthly_sip),
            equity_percent=None if args.equity_percent is None else _money(args.equity_percent),
            target_year=args.target_year,
            step_up_rate=None if args.step_up_rate is None else _money(args.step_up_rate),
        )
        result = simulation_service.run_simulation(
            ctx.db, ctx.user, goal, SimulationRequest(overrides=overrides), ctx.today
        )
    except ValidationError as error:
        raise ToolError(error.errors()[0]["msg"]) from None
    except simulation_service.SimulationUnavailable as error:
        raise ToolError(str(error)) from None
    inputs = result.inputs
    data = {
        "goal": goal.name,
        "model": result.model,
        "paths": result.paths,
        "chance_of_success_percent": result.success_probability,
        "starts_from": start_source,
        "inputs": inputs.model_dump(),
        "final_value_percentiles": result.final.model_dump(),
        "median_shortfall_of_failing_paths": result.median_shortfall,
        "monthly_sip_for_chance": [r.model_dump() for r in result.required_sip],
        "single_return_projection": result.deterministic.model_dump(),
        "portfolio_volatility_percent": result.annual_volatility,
    }
    what_if = [
        text
        for value, text in (
            (args.monthly_sip, f"SIP {inr(args.monthly_sip or 0)}"),
            (args.equity_percent, f"{args.equity_percent:g}% equity"),
            (args.target_year, f"target {args.target_year}"),
            (args.step_up_rate, f"{args.step_up_rate:g}% step-up"),
            (args.current_savings, f"starting from {inr(args.current_savings or 0)}"),
        )
        if value is not None
    ]
    chart = {
        "type": "simulation",
        "title": f"{goal.name}: simulated value each year"
        + (f" (what if: {', '.join(what_if)})" if what_if else ""),
        "bands": [b.model_dump() for b in result.bands],
        "target": inputs.inflated_target,
    }
    return ToolOutput(data, chart)


class RecommendationArgs(BaseModel):
    goal_id: int
    refresh: bool = Field(default=False, description="Make a new one with today's data")


def get_recommendation(ctx: ToolContext, args: RecommendationArgs) -> ToolOutput:
    goal = _owned_goal(ctx, args.goal_id)
    found = recommendation_service.history_for(ctx.db, goal)
    try:
        stored = (
            recommendation_service.recommend(ctx.db, ctx.user, goal, ctx.today)
            if args.refresh or not found
            else found[0]
        )
    except recommendation_service.RecommendationUnavailable as error:
        raise ToolError(str(error)) from None
    rec = recommendation_service.to_read(stored)
    data = {
        "goal": goal.name,
        "made_on": rec.created_at.date().isoformat(),
        "years_to_goal": rec.years_to_goal,
        "risk_category": rec.risk_category,
        "equity_percent": rec.equity_share,
        "expected_return_percent": rec.expected_return,
        "volatility_percent": rec.volatility,
        "allocation": [{"part": a.label, "percent": a.weight} for a in rec.allocation],
        "funds": [
            {"fund": f.name, "part": f.sleeve_label, "percent": f.weight, "why": f.reason}
            for f in rec.funds
        ],
        "reasons": rec.reasons,
    }
    chart = {
        "type": "allocation",
        "title": f"{goal.name}: recommended allocation",
        "allocation": [a.model_dump() for a in rec.allocation],
    }
    return ToolOutput(data, chart)


# --- Funds -----------------------------------------------------------------------------------

_METRICS = ("return_1y", "return_3y", "return_5y", "volatility", "sharpe", "max_drawdown")


class FundSearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=80, description="Fund name or fund house")
    limit: int = Field(default=5, ge=1, le=8)


def get_fund_metrics(ctx: ToolContext, args: FundSearchArgs) -> ToolOutput:
    page = fund_service.list_funds(
        ctx.db, q=args.query, plan="direct", option="growth", page_size=args.limit
    )
    if not page.items:  # perhaps only regular or IDCW plans match
        page = fund_service.list_funds(ctx.db, q=args.query, page_size=args.limit)
    funds = [
        {
            "fund_id": f.id,
            "name": f.name,
            "plan": f.plan,
            "option": f.option,
            "category": f.category,
            "latest_nav": float(f.latest_nav) if f.latest_nav is not None else None,
            "nav_date": f.latest_nav_date.isoformat() if f.latest_nav_date else None,
            **{f"{m}_percent" if m != "sharpe" else m: getattr(f, m) for m in _METRICS},
        }
        for f in page.items
    ]
    return ToolOutput(
        {
            "matches": page.total,
            "funds": funds,
            "note": "Returns are CAGR %, volatility and drawdown over 3 years; Sharpe uses 6%.",
        }
    )


class CompareArgs(BaseModel):
    fund_ids: list[int] = Field(min_length=2, max_length=4, description="From get_fund_metrics")


def compare_funds(ctx: ToolContext, args: CompareArgs) -> ToolOutput:
    rows = []
    for fund_id in args.fund_ids:
        fund = fund_service.get_fund(ctx.db, fund_id)
        if fund is None:
            raise ToolError(f"No fund with id {fund_id}; use get_fund_metrics to find ids.")
        detail = fund_service.to_detail(ctx.db, fund)
        metrics = detail.metrics
        rows.append(
            {
                "fund_id": fund.id,
                "name": fund.name,
                "plan": fund.plan,
                "category": fund.category,
                "history_start": metrics.history_start.isoformat() if metrics else None,
                **{m: (getattr(metrics, m) if metrics else None) for m in _METRICS},
                "rolling_3y_min": metrics.rolling_3y_min if metrics else None,
                "rolling_3y_positive": metrics.rolling_3y_positive if metrics else None,
            }
        )
    chart = {"type": "fund_table", "title": "Fund comparison", "funds": rows}
    return ToolOutput({"funds": rows, "note": "Percentages except sharpe."}, chart)


# --- Portfolio and profile ------------------------------------------------------------------------


def get_portfolio_status(ctx: ToolContext, _: NoArgs) -> ToolOutput:
    p = portfolio_service.portfolio(ctx.db, ctx.user, ctx.today)
    holdings = sorted((h for h in p.holdings if h.units > 0), key=lambda h: -h.value)
    return ToolOutput(
        {
            "totals": p.totals.model_dump(mode="json"),
            "goals": [
                g.model_dump(
                    include={
                        "goal_id", "name", "status", "value", "cost", "xirr", "expected_return",
                        "plan_value", "vs_plan", "projected_value", "inflated_target",
                        "required_sip", "monthly_sip", "rebalance_needed", "equity_actual",
                        "equity_target",
                    }
                )
                for g in p.goals
            ],
            "alerts": [f"{a.goal_name}: {a.message}" for a in p.alerts],
            "holdings": [
                {"fund": h.fund_name, "goal": h.goal_name, "value": h.value, "cost": h.cost,
                 "gain_percent": h.gain_percent, "xirr": h.xirr}
                for h in holdings[:10]
            ],
            "note": "xirr is % a year (null under a year); amounts in rupees.",
        }
    )  # fmt: skip


def get_risk_profile(ctx: ToolContext, _: NoArgs) -> ToolOutput:
    assessment = latest_assessment(ctx.db, ctx.user)
    profile = profile_service.get_profile(ctx.db, ctx.user)
    data: dict[str, Any] = {"has_financial_profile": profile is not None}
    if profile is not None:
        today = ctx.today or date.today()
        birthday = profile.date_of_birth
        # Only what planning needs: age and money, never the date of birth itself.
        data["age"] = (
            today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
        )
        data["monthly_income"] = float(profile.monthly_income)
        data["monthly_expenses"] = float(profile.monthly_expenses)
        data["monthly_emi"] = float(profile.monthly_emi)
        data["monthly_surplus"] = float(
            profile.monthly_income - profile.monthly_expenses - profile.monthly_emi
        )
        data["dependants"] = profile.dependents
    if assessment is not None:
        data["risk"] = {
            "category": assessment.category,
            "final_score": assessment.final_score,
            "tolerance_score": assessment.tolerance_score,
            "capacity_score": assessment.capacity_score,
            "taken_on": assessment.created_at.date().isoformat(),
        }
    return ToolOutput(data)  # fmt: skip


# --- Knowledge base --------------------------------------------------------------------------


class ExplainArgs(BaseModel):
    question: str = Field(min_length=2, max_length=300, description="The term or question")


def explain_term(ctx: ToolContext, args: ExplainArgs) -> ToolOutput:
    if rag.is_empty(ctx.db):
        rag.ingest(ctx.db, ctx.llm)  # first use: build the knowledge base
    passages = rag.search(ctx.db, ctx.llm, args.question)
    relevant = [p for p in passages if p.similarity >= RELEVANT_SIMILARITY]
    if not relevant:
        return ToolOutput(
            {"passages": [], "note": "Nothing in the knowledge base covers this question."}
        )
    return ToolOutput(
        {
            "passages": [
                {"source": f"{p.title} - {p.heading}", "text": p.content,
                 "similarity": p.similarity}
                for p in relevant
            ],
            "note": "Explain using these passages and name the source titles.",
        }
    )  # fmt: skip


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "list_goals",
            "List the user's saved financial goals with ids, targets, SIPs and whether each is "
            "on track (single assumed return). Call first when the user refers to their goals.",
            NoArgs,
            list_goals,
        ),
        Tool(
            "goal_calculator",
            "Work out the inflated target, projected value and required monthly SIP for a goal "
            "that is NOT saved (what-if questions such as 'how much SIP for 50 lakh in 15 "
            "years?'). Nothing is saved.",
            CalculatorArgs,
            goal_calculator,
        ),
        Tool(
            "create_goal",
            "Save a new goal for the user. First call it with confirmed=false to get a preview, "
            "show the details and ask the user; call again with confirmed=true only after the "
            "user agrees in the chat. Retirement is planned on the Retirement page instead.",
            CreateGoalArgs,
            create_goal,
        ),
        Tool(
            "run_simulation",
            "Monte Carlo simulation of a saved goal (10,000 market paths): the chance of "
            "reaching the target, the range of outcomes, and the SIP needed for a 50/75/90% "
            "chance. Optional what-if changes to SIP, equity share, step-up or target year.",
            SimulationArgs,
            run_simulation,
        ),
        Tool(
            "get_recommendation",
            "The recommended asset allocation and funds for a saved goal, with reasons. Uses "
            "the latest stored recommendation, or makes one if there is none or refresh=true.",
            RecommendationArgs,
            get_recommendation,
        ),
        Tool(
            "get_fund_metrics",
            "Search mutual funds by name or fund house and return their returns, volatility, "
            "Sharpe ratio and worst fall (direct growth plans first) with fund ids.",
            FundSearchArgs,
            get_fund_metrics,
        ),
        Tool(
            "compare_funds",
            "Compare 2 to 4 funds side by side by id (from get_fund_metrics): returns, risk and "
            "consistency of rolling 3-year returns.",
            CompareArgs,
            compare_funds,
        ),
        Tool(
            "get_portfolio_status",
            "The user's recorded investments: totals and XIRR, each goal's status against its "
            "plan, rebalancing and other alerts, and the largest holdings.",
            NoArgs,
            get_portfolio_status,
        ),
        Tool(
            "get_risk_profile",
            "The user's risk category and scores and their monthly income, expenses and surplus "
            "from the financial profile.",
            NoArgs,
            get_risk_profile,
        ),
        Tool(
            "explain_term",
            "Search the investor-education knowledge base to explain a term or concept (SIP, "
            "XIRR, expense ratio, debt fund risk, rebalancing, taxes in general, how GoalWise "
            "calculates things). Use for every explanation.",
            ExplainArgs,
            explain_term,
        ),
    )
}


@dataclass(frozen=True)
class Execution:
    data: dict[str, Any]
    chart: dict[str, Any] | None
    status: Literal["ok", "error"]
    latency_ms: int


def execute(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> Execution:
    """Validate the model's arguments and run the tool; every failure becomes data, not a crash."""
    started = time.perf_counter()
    tool = TOOLS.get(name)
    try:
        if tool is None:
            raise ToolError(f"Unknown tool {name!r}.")
        try:
            args = tool.args.model_validate(arguments)
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "arguments"
            raise ToolError(f"Invalid {where}: {first['msg']}") from None
        output = tool.run(ctx, args)
        data, chart, status = output.data, output.chart, "ok"
    except ToolError as error:
        data, chart, status = {"error": str(error)}, None, "error"
    except Exception:  # a bug or a database error: keep the conversation alive, log the cause
        logger.exception("Tool %s failed", name)
        ctx.db.rollback()
        data, chart, status = {"error": "The calculation failed unexpectedly."}, None, "error"
    elapsed = round((time.perf_counter() - started) * 1000)
    return Execution(data, chart, status, elapsed)
