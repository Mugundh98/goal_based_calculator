"""Rule-based risk profiling.

Risk profile = the LOWER of two scores (each 0-100):

* Risk tolerance - the investor's WILLINGNESS to take risk, from a questionnaire.
* Risk capacity  - the investor's financial ABILITY to absorb losses, computed from their
  financial profile (age, savings rate, emergency fund, debt, dependants, job stability).

Taking the lower score follows standard suitability practice: someone eager to take risk
but unable to afford losses should not get an aggressive portfolio, and vice versa.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

QUESTIONNAIRE_VERSION = "v1"

CATEGORIES = ("conservative", "moderate", "aggressive")


# --- Questionnaire (risk tolerance) -----------------------------------------------------------


@dataclass(frozen=True)
class Option:
    id: str
    text: str
    points: int


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    options: tuple[Option, ...]

    @property
    def max_points(self) -> int:
        return max(option.points for option in self.options)


QUESTIONS: tuple[Question, ...] = (
    Question(
        "objective",
        "What is your main goal when investing?",
        (
            Option("a", "Protect my money; I cannot accept losses", 0),
            Option("b", "Earn a steady income", 1),
            Option("c", "A balance of income and growth", 2),
            Option("d", "Long-term growth", 3),
            Option("e", "Maximum growth, even with large ups and downs", 4),
        ),
    ),
    Question(
        "experience",
        "Which investments have you held before?",
        (
            Option("a", "None, or only a savings account", 0),
            Option("b", "Fixed deposits, PPF or other guaranteed products", 1),
            Option("c", "Mutual funds (debt or hybrid)", 2),
            Option("d", "Equity mutual funds or shares for several years", 3),
            Option("e", "Active share trading or derivatives", 4),
        ),
    ),
    Question(
        "drawdown_reaction",
        "Your investments fall 20% in one month. What do you do?",
        (
            Option("a", "Sell everything to stop further losses", 0),
            Option("b", "Sell some of it", 1),
            Option("c", "Do nothing and wait", 2),
            Option("d", "Invest a little more", 3),
            Option("e", "Invest a lot more; prices are low", 4),
        ),
    ),
    Question(
        "portfolio_choice",
        "Which portfolio would you choose? (best year / worst year)",
        (
            Option("a", "+8% / -2%", 0),
            Option("b", "+14% / -8%", 1),
            Option("c", "+20% / -15%", 2),
            Option("d", "+28% / -25%", 3),
            Option("e", "+35% / -35%", 4),
        ),
    ),
    Question(
        "risk_word",
        'Which word do you most associate with "risk"?',
        (
            Option("a", "Danger", 0),
            Option("b", "Uncertainty", 1),
            Option("c", "Opportunity", 3),
            Option("d", "Thrill", 4),
        ),
    ),
    Question(
        "equity_share",
        "What share of your long-term savings would you put in equity (shares)?",
        (
            Option("a", "Less than 10%", 0),
            Option("b", "10% to 25%", 1),
            Option("c", "25% to 50%", 2),
            Option("d", "50% to 75%", 3),
            Option("e", "More than 75%", 4),
        ),
    ),
    Question(
        "knowledge",
        "How would you rate your knowledge of investing?",
        (
            Option("a", "Very low", 0),
            Option("b", "Basic", 1),
            Option("c", "Average", 2),
            Option("d", "Good", 3),
            Option("e", "Expert", 4),
        ),
    ),
)

_QUESTIONS_BY_ID = {question.id: question for question in QUESTIONS}


class InvalidAnswersError(ValueError):
    pass


def tolerance_score(answers: dict[str, str]) -> int:
    """Scale the questionnaire points to 0-100. Every question must be answered exactly once."""
    missing = [q.id for q in QUESTIONS if q.id not in answers]
    if missing:
        raise InvalidAnswersError(f"Unanswered questions: {', '.join(missing)}")
    unknown = [q_id for q_id in answers if q_id not in _QUESTIONS_BY_ID]
    if unknown:
        raise InvalidAnswersError(f"Unknown questions: {', '.join(unknown)}")

    earned = 0
    for question in QUESTIONS:
        option = next((o for o in question.options if o.id == answers[question.id]), None)
        if option is None:
            raise InvalidAnswersError(f"Invalid option for question '{question.id}'")
        earned += option.points

    maximum = sum(q.max_points for q in QUESTIONS)
    return round(earned / maximum * 100)


# --- Financial capacity ------------------------------------------------------------------------


@dataclass(frozen=True)
class CapacityInputs:
    age: int
    employment_type: str
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_emi: Decimal
    current_savings: Decimal
    dependents: int


@dataclass(frozen=True)
class Factor:
    """One line of the capacity breakdown shown to the user."""

    key: str
    label: str
    value: str  # human-readable input, e.g. "4.5 months"
    points: int
    max_points: int


EMPLOYMENT_POINTS = {
    "salaried": 15,
    "business_owner": 10,
    "self_employed": 8,
    "retired": 5,
    "other": 5,
}


def age_on(date_of_birth: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def _age_points(age: int) -> int:
    if age < 30:
        return 25
    if age < 40:
        return 20
    if age < 50:
        return 15
    if age < 60:
        return 8
    return 3


def _savings_rate_points(rate: Decimal | None) -> int:
    if rate is None or rate <= 0:
        return 0
    if rate >= Decimal("0.40"):
        return 20
    if rate >= Decimal("0.25"):
        return 15
    if rate >= Decimal("0.10"):
        return 10
    return 5


def _emergency_points(months: Decimal | None) -> int:
    if months is None or months >= 6:  # None = no monthly outgoings to cover
        return 15
    if months >= 3:
        return 10
    if months >= 1:
        return 5
    return 0


def _debt_points(ratio: Decimal | None) -> int:
    if ratio is None:  # EMI but no income
        return 0
    if ratio == 0:
        return 15
    if ratio < Decimal("0.20"):
        return 12
    if ratio < Decimal("0.40"):
        return 6
    return 0


def _dependents_points(dependents: int) -> int:
    if dependents == 0:
        return 10
    if dependents <= 2:
        return 6
    return 2


def capacity_factors(inputs: CapacityInputs) -> list[Factor]:
    income = inputs.monthly_income
    outgoings = inputs.monthly_expenses + inputs.monthly_emi

    savings_rate = (income - outgoings) / income if income > 0 else None
    emergency_months = inputs.current_savings / outgoings if outgoings > 0 else None
    if inputs.monthly_emi == 0:
        debt_ratio: Decimal | None = Decimal(0)
    elif income > 0:
        debt_ratio = inputs.monthly_emi / income
    else:
        debt_ratio = None

    def pct(value: Decimal | None) -> str:
        return "n/a" if value is None else f"{value * 100:.0f}%"

    return [
        Factor("age", "Age", f"{inputs.age} years", _age_points(inputs.age), 25),
        Factor(
            "savings_rate",
            "Monthly savings rate",
            pct(savings_rate),
            _savings_rate_points(savings_rate),
            20,
        ),
        Factor(
            "emergency_fund",
            "Emergency fund",
            "no outgoings" if emergency_months is None else f"{emergency_months:.1f} months",
            _emergency_points(emergency_months),
            15,
        ),
        Factor("debt_burden", "Loan EMIs / income", pct(debt_ratio), _debt_points(debt_ratio), 15),
        Factor(
            "dependents",
            "Dependants",
            str(inputs.dependents),
            _dependents_points(inputs.dependents),
            10,
        ),
        Factor(
            "employment",
            "Income stability",
            inputs.employment_type.replace("_", " "),
            EMPLOYMENT_POINTS[inputs.employment_type],
            15,
        ),
    ]


def capacity_score(factors: list[Factor]) -> int:
    return sum(f.points for f in factors)  # maximum points add up to 100


# --- Combining ---------------------------------------------------------------------------------


def category_for(score: int) -> str:
    if score < 40:
        return "conservative"
    if score < 70:
        return "moderate"
    return "aggressive"


def final_profile(tolerance: int, capacity: int) -> tuple[int, str]:
    score = min(tolerance, capacity)
    return score, category_for(score)


def explanation(tolerance: int, capacity: int) -> str:
    tol_cat, cap_cat = category_for(tolerance), category_for(capacity)
    if tol_cat == cap_cat:
        return f"Your willingness and your financial capacity both point to a {tol_cat} profile."
    if CATEGORIES.index(tol_cat) > CATEGORIES.index(cap_cat):
        return (
            f"You are willing to take {tol_cat} risk, but your finances support a {cap_cat} "
            "profile, so the lower one is used."
        )
    return (
        f"Your finances could support {cap_cat} risk, but you prefer {tol_cat} investing, "
        "so your preference is respected."
    )
