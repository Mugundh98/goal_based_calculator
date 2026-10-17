"""The "Download my plan" PDF, rendered server-side with ReportLab.

Pure: `render(PlanReport) -> bytes`; the data is gathered by services/reports.py. ReportLab is
pure Python (no browser or system libraries), so the same code runs on Windows and on a Linux
server. Amounts are written "Rs 1,25,000": the PDF's built-in fonts have no ₹ glyph, and
embedding a font only for one character would add weight to every file.
"""

from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.finance.formatting import inr, lakh_crore

RS = "Rs "
EMERALD = colors.HexColor("#047857")
AMBER = colors.HexColor("#b45309")
SLATE = colors.HexColor("#475569")
LIGHT = colors.HexColor("#f1f5f9")
LINE = colors.HexColor("#e2e8f0")
# The app's categorical palette, in the same fixed order (lib/chart.ts).
SLEEVE_COLOURS = {
    "large_cap": colors.HexColor("#2a78d6"),
    "mid_small_cap": colors.HexColor("#eb6834"),
    "long_debt": colors.HexColor("#1baf7a"),
    "short_debt": colors.HexColor("#eda100"),
}
DISCLAIMER = (
    "GoalWise is an educational planning tool, not investment advice. Projections use assumed "
    "returns and past market data; actual returns will differ. Taxes, exit loads and costs "
    "other than stamp duty are not included."
)


def money(amount: float | None) -> str:
    return "-" if amount is None else inr(amount, RS)


def big(amount: float | None) -> str:
    return "-" if amount is None else lakh_crore(amount, RS)


def pct(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}%"


# --- Data --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileSection:
    age: int
    employment: str
    monthly_income: float
    monthly_expenses: float
    monthly_emi: float
    monthly_surplus: float
    savings: float
    investments: float
    dependants: int
    risk_category: str | None = None
    risk_score: int | None = None
    tolerance_score: int | None = None
    capacity_score: int | None = None
    assessed_on: date | None = None


@dataclass(frozen=True)
class Allocation:
    sleeve: str
    label: str
    weight: float  # percent


@dataclass(frozen=True)
class FundPick:
    name: str
    part: str
    weight: float  # percent of the goal


@dataclass(frozen=True)
class SimulationSummary:
    run_on: date
    model: str
    chance: float  # percent
    p10: float
    p50: float
    p90: float
    sip_for_90: float | None


@dataclass(frozen=True)
class Tracking:
    status: str  # on_track / off_track
    value: float
    cost: float
    xirr: float | None
    plan_value: float
    rebalance_needed: bool | None


@dataclass(frozen=True)
class GoalSection:
    name: str
    goal_type: str
    target_year: int
    years: int
    cost_today: float
    inflation: float
    inflated_target: float
    current_savings: float
    monthly_sip: float
    step_up: float
    expected_return: float
    projected_value: float
    funded_percent: float
    on_track: bool
    required_sip: float | None
    allocation: list[Allocation] = field(default_factory=list)
    recommended_on: date | None = None
    recommended_return: float | None = None
    funds: list[FundPick] = field(default_factory=list)
    simulation: SimulationSummary | None = None
    tracking: Tracking | None = None


@dataclass(frozen=True)
class RetirementSection:
    current_age: int
    retirement_age: int
    life_expectancy: int
    monthly_expense_today: float
    corpus_needed: float
    corpus_needed_today: float
    projected_corpus: float
    required_sip: float | None
    monthly_sip: float
    withdrawal_rate: float
    money_lasts_until: float | None


@dataclass(frozen=True)
class HoldingRow:
    fund: str
    goal: str
    value: float
    cost: float
    xirr: float | None


@dataclass(frozen=True)
class PortfolioSection:
    value: float
    cost: float
    xirr: float | None
    as_of: date | None
    holdings: list[HoldingRow]
    alerts: list[str]


@dataclass(frozen=True)
class PlanReport:
    name: str
    generated_on: date
    profile: ProfileSection | None
    goals: list[GoalSection]
    retirement: RetirementSection | None
    portfolio: PortfolioSection | None
    data_as_of: date | None  # newest NAV in the database


# --- Rendering ---------------------------------------------------------------------------------

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle(
        "title",
        parent=_base["Title"],
        fontSize=20,
        leading=24,
        textColor=EMERALD,
        alignment=0,
        spaceAfter=2 * mm,
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=_base["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.black,
        spaceBefore=6 * mm,
        spaceAfter=2 * mm,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=_base["Heading3"],
        fontSize=11.5,
        leading=15,
        spaceBefore=4 * mm,
        spaceAfter=1.5 * mm,
    ),
    "body": ParagraphStyle("body", parent=_base["BodyText"], fontSize=9.5, leading=13),
    "small": ParagraphStyle(
        "small", parent=_base["BodyText"], fontSize=8, leading=10.5, textColor=SLATE
    ),
    "cell": ParagraphStyle("cell", parent=_base["BodyText"], fontSize=8.5, leading=11),
}


def P(text: str, style: str = "body") -> Paragraph:
    # Text from elsewhere in the app (alerts, reasons) may contain glyphs the built-in fonts
    # lack: the rupee sign and the true minus sign.
    return Paragraph(text.replace("₹", RS).replace("−", "-"), STYLES[style])


def _table(rows: list[list[object]], widths: list[float], header: bool = True) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), SLATE),
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ]
    table.setStyle(TableStyle(style))
    return table


def _facts(pairs: list[tuple[str, str]], width: float) -> Table:
    """Label/value pairs in two columns of pairs."""
    rows = []
    for i in range(0, len(pairs), 2):
        row: list[object] = []
        for label, value in pairs[i : i + 2]:
            row += [P(escape(label), "small"), P(f"<b>{escape(value)}</b>", "cell")]
        rows.append(row + [""] * (4 - len(row)))
    table = Table(rows, colWidths=[width * 0.22, width * 0.28] * 2)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _bar(percent: float, width: float, colour: colors.Color) -> Drawing:
    """A progress bar, 0-100%."""
    drawing = Drawing(width, 9)
    drawing.add(Rect(0, 2, width, 6, fillColor=LIGHT, strokeColor=None))
    drawing.add(
        Rect(0, 2, width * min(max(percent, 0), 100) / 100, 6, fillColor=colour, strokeColor=None)
    )
    return drawing


def _allocation_bar(allocation: list[Allocation], width: float) -> Drawing:
    """One bar split by sleeve, with a legend underneath (the app's allocation bar)."""
    shown = [a for a in allocation if a.weight > 0]
    drawing = Drawing(width, 34)
    x = 0.0
    for a in shown:
        w = width * a.weight / 100
        drawing.add(
            Rect(
                x,
                22,
                max(w - 1, 0.5),
                10,
                fillColor=SLEEVE_COLOURS.get(a.sleeve, SLATE),
                strokeColor=None,
            )
        )
        x += w
    x = 0.0
    for a in shown:
        drawing.add(
            Rect(x, 8, 7, 7, fillColor=SLEEVE_COLOURS.get(a.sleeve, SLATE), strokeColor=None)
        )
        label = f"{a.label} {a.weight:g}%"
        drawing.add(String(x + 10, 9, label, fontName="Helvetica", fontSize=7.5, fillColor=SLATE))
        x += 14 + len(label) * 3.7
    return drawing


def _summary(plan: PlanReport, width: float) -> list[object]:
    sip_now = sum(g.monthly_sip for g in plan.goals)
    sip_needed = sum(g.required_sip or 0 for g in plan.goals)
    on_track = sum(1 for g in plan.goals if g.on_track)
    pairs = [
        ("Goals", f"{len(plan.goals)} ({on_track} on track)"),
        (
            "Risk profile",
            (plan.profile.risk_category or "not assessed").capitalize()
            if plan.profile
            else "not assessed",
        ),
        ("Invested each month now", money(sip_now)),
        ("Needed each month for all goals", money(sip_needed)),
    ]
    if plan.profile:
        pairs.append(("Left to invest each month", money(plan.profile.monthly_surplus)))
    if plan.portfolio:
        pairs.append(("Investments recorded", big(plan.portfolio.value)))
    return [_facts(pairs, width)]


def _profile(profile: ProfileSection, width: float) -> list[object]:
    pairs = [
        ("Age", str(profile.age)),
        ("Employment", profile.employment.replace("_", " ").capitalize()),
        ("Monthly income", money(profile.monthly_income)),
        ("Monthly expenses", money(profile.monthly_expenses)),
        ("Loan EMIs", money(profile.monthly_emi)),
        ("Left each month", money(profile.monthly_surplus)),
        ("Savings", money(profile.savings)),
        ("Other investments", money(profile.investments)),
        ("Dependants", str(profile.dependants)),
    ]
    out: list[object] = [P("About you", "h1"), _facts(pairs, width)]
    if profile.risk_category:
        out += [
            P("Risk profile", "h2"),
            P(
                f"<b>{escape(profile.risk_category.capitalize())}</b> - score {profile.risk_score}"
                f"/100 (willingness {profile.tolerance_score}, financial capacity "
                f"{profile.capacity_score}; the lower of the two counts), assessed on "
                f"{profile.assessed_on:%d %b %Y}."
            ),
        ]
    return out


def _goals_table(goals: list[GoalSection], width: float) -> Table:
    rows: list[list[object]] = [
        ["Goal", "Year", "Cost today", "Target", "SIP now", "SIP needed", "Status"]
    ]
    for g in goals:
        status = g.tracking.status if g.tracking else ("on_track" if g.on_track else "off_track")
        rows.append(
            [
                P(escape(g.name), "cell"),
                str(g.target_year),
                big(g.cost_today),
                big(g.inflated_target),
                money(g.monthly_sip),
                money(g.required_sip),
                "On track" if status == "on_track" else "Needs more",
            ]
        )
    return _table(rows, [width * f for f in (0.24, 0.08, 0.13, 0.13, 0.13, 0.15, 0.14)])


def _goal(goal: GoalSection, width: float) -> list[object]:
    head = P(
        f"{escape(goal.name)} <font size=9 color='#475569'>"
        f"{escape(goal.goal_type.replace('_', ' ').capitalize())} - {goal.target_year} "
        f"(in {goal.years} years)</font>",
        "h2",
    )
    pairs = [
        ("Cost today", money(goal.cost_today)),
        (
            f"Target in {goal.target_year} ({goal.inflation:g}% inflation)",
            money(goal.inflated_target),
        ),
        ("Invested now" if goal.tracking else "Saved for it", money(goal.current_savings)),
        (
            "SIP now" + (f" (+{goal.step_up:g}% a year)" if goal.step_up else ""),
            money(goal.monthly_sip),
        ),
        ("Assumed return", pct(goal.expected_return)),
        ("Projected value", money(goal.projected_value)),
        ("SIP needed", money(goal.required_sip)),
        ("Funded", pct(goal.funded_percent)),
    ]
    colour = EMERALD if goal.on_track else AMBER
    block: list[object] = [head, _facts(pairs, width), _bar(goal.funded_percent, width, colour)]
    if goal.tracking:
        t = goal.tracking
        block.append(
            P(
                f"<b>Investments recorded:</b> worth {money(t.value)} (invested {money(t.cost)}), "
                f"XIRR {pct(t.xirr, 2)}; the plan expected {money(t.plan_value)} by now. "
                + (
                    "<font color='#b45309'>The mix has drifted from the recommendation: "
                    "rebalancing is due.</font>"
                    if t.rebalance_needed
                    else ""
                ),
                "small",
            )
        )
    if goal.simulation:
        s = goal.simulation
        block.append(
            P(
                f"<b>Simulation</b> ({s.model}, {s.run_on:%d %b %Y}): {pct(s.chance)} chance of "
                f"reaching the target; middle outcome {big(s.p50)}, 1 in 10 below {big(s.p10)}, "
                f"1 in 10 above {big(s.p90)}"
                + (f"; SIP for a 90% chance {money(s.sip_for_90)}." if s.sip_for_90 else "."),
                "small",
            )
        )
    if goal.allocation:
        block += [
            Spacer(1, 2 * mm),
            P(
                f"<b>Recommended allocation</b> ({goal.recommended_on:%d %b %Y}, expected "
                f"{pct(goal.recommended_return)} a year)",
                "small",
            ),
            _allocation_bar(goal.allocation, width),
        ]
        if goal.funds:
            rows: list[list[object]] = [["Fund", "Part", "Share of the goal"]]
            rows += [[P(escape(f.name), "cell"), f.part, pct(f.weight)] for f in goal.funds]
            block.append(_table(rows, [width * 0.55, width * 0.27, width * 0.18]))
    return [KeepTogether(block[:4]), *block[4:]]


def _retirement(r: RetirementSection, width: float) -> list[object]:
    pairs = [
        ("Age now / retire at", f"{r.current_age} / {r.retirement_age}"),
        ("Plan until age", str(r.life_expectancy)),
        ("Monthly spending (today's money)", money(r.monthly_expense_today)),
        ("Corpus needed at retirement", big(r.corpus_needed)),
        ("The same in today's money", big(r.corpus_needed_today)),
        ("Withdrawal rate", pct(r.withdrawal_rate, 2) + " (the 4% rule: 4%)"),
        ("Corpus the current plan reaches", big(r.projected_corpus)),
        ("SIP now / needed", f"{money(r.monthly_sip)} / {money(r.required_sip)}"),
    ]
    lasts = (
        "The money lasts until the planned age."
        if r.money_lasts_until is None
        else f"With the current plan the money runs out at about age {r.money_lasts_until:.0f}."
    )
    return [P("Retirement", "h1"), _facts(pairs, width), P(lasts, "small")]


def _portfolio(p: PortfolioSection, width: float) -> list[object]:
    out: list[object] = [
        P("Your investments", "h1"),
        P(
            f"Worth <b>{money(p.value)}</b>, invested {money(p.cost)}, XIRR {pct(p.xirr, 2)}"
            + (f" (NAVs of {p.as_of:%d %b %Y})." if p.as_of else ".")
        ),
    ]
    if p.holdings:
        rows: list[list[object]] = [["Fund", "Goal", "Invested", "Value", "XIRR"]]
        rows += [
            [
                P(escape(h.fund), "cell"),
                P(escape(h.goal), "cell"),
                money(h.cost),
                money(h.value),
                pct(h.xirr, 2),
            ]
            for h in p.holdings
        ]
        out.append(_table(rows, [width * f for f in (0.38, 0.2, 0.15, 0.15, 0.12)]))
    if p.alerts:
        out.append(P("Alerts", "h2"))
        out += [P(f"- {escape(a)}", "small") for a in p.alerts]
    return out


def render(plan: PlanReport) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"GoalWise plan - {plan.name}",
        author="GoalWise",
        subject="Financial plan",
    )
    width = doc.width

    def footer(canvas, document) -> None:  # noqa: ANN001 - ReportLab's callback signature
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(
            document.leftMargin,
            10 * mm,
            f"GoalWise - plan for {plan.name} - {plan.generated_on:%d %b %Y}",
        )
        canvas.drawRightString(
            document.leftMargin + document.width, 10 * mm, f"Page {document.page}"
        )
        canvas.restoreState()

    story: list[object] = [
        P("Your financial plan", "title"),
        P(
            f"Prepared for <b>{escape(plan.name)}</b> on {plan.generated_on:%d %B %Y}"
            + (f", with market data up to {plan.data_as_of:%d %b %Y}" if plan.data_as_of else "")
            + ".",
            "body",
        ),
        Spacer(1, 3 * mm),
        *_summary(plan, width),
    ]
    if plan.profile:
        story += _profile(plan.profile, width)
    story.append(P("Your goals", "h1"))
    if plan.goals:
        story.append(_goals_table(plan.goals, width))
        for goal in plan.goals:
            story += _goal(goal, width)
    else:
        story.append(P("No goals yet. Add goals in GoalWise to see them planned here."))
    if plan.retirement:
        story += _retirement(plan.retirement, width)
    if plan.portfolio and plan.portfolio.holdings:
        story += _portfolio(plan.portfolio, width)
    story += [
        P("Assumptions and notes", "h1"),
        P(
            "Goal costs are inflated to their target year. Returns are planning assumptions "
            "(from the risk profile unless set for a goal); SIPs are invested at the start of each "
            "month. Simulations draw thousands of market paths from past Indian data. "
            "Recommendations follow the glide path and mean-variance rules described in the app.",
            "small",
        ),
        Spacer(1, 2 * mm),
        P(DISCLAIMER, "small"),
    ]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
