"""Time value of money: the formulas every goal calculation is built from.

Pure functions only - no database, no HTTP - so each one can be checked against a hand
calculation. Conventions used throughout:

* Rates are FRACTIONS per year: 12% is passed as 0.12 (the API layer converts from percent).
* Returns compound monthly at the EFFECTIVE monthly rate (1 + r)^(1/12) - 1, so "12% a year"
  means the same growth for a lump sum and for a SIP. (Many online calculators use r / 12
  instead, which quietly assumes a slightly higher annual return of 12.68%.)
* A SIP instalment is invested at the START of each month (annuity due), as SIPs are in
  practice: the first instalment already earns one month of return.
* Results are plain floats. These are projections built on assumed rates, so float error
  (~1e-12) is irrelevant next to the uncertainty of the rate itself; money that is STORED stays
  exact NUMERIC in the database (see ADR-006).
"""

MONTHS_PER_YEAR = 12


class FinanceInputError(ValueError):
    """An input that makes a formula meaningless (negative period, rate <= -100%, ...)."""


def _check_period(value: float, name: str) -> None:
    if value < 0:
        raise FinanceInputError(f"{name} cannot be negative")


def _check_rate(rate: float, name: str = "rate") -> None:
    if rate <= -1:
        raise FinanceInputError(f"{name} must be greater than -100%")


# --- Rates ------------------------------------------------------------------------------------


def monthly_rate(annual_rate: float) -> float:
    """Effective monthly rate equivalent to an annual rate: (1 + r)^(1/12) - 1."""
    _check_rate(annual_rate)
    return (1 + annual_rate) ** (1 / MONTHS_PER_YEAR) - 1


def real_return(nominal_rate: float, inflation_rate: float) -> float:
    """Return after inflation (Fisher equation): (1 + n) / (1 + i) - 1.

    The shortcut n - i overstates it: 12% nominal with 6% inflation is 5.66% real, not 6%.
    """
    _check_rate(nominal_rate, "nominal rate")
    _check_rate(inflation_rate, "inflation rate")
    return (1 + nominal_rate) / (1 + inflation_rate) - 1


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate: (end / start)^(1 / years) - 1."""
    if start_value <= 0 or end_value < 0:
        raise FinanceInputError("start value must be positive and end value non-negative")
    if years <= 0:
        raise FinanceInputError("years must be positive")
    return (end_value / start_value) ** (1 / years) - 1


# --- Lump sums --------------------------------------------------------------------------------


def future_value(present_value: float, annual_rate: float, years: float) -> float:
    """What a lump sum grows to: FV = PV * (1 + r)^n."""
    _check_rate(annual_rate)
    _check_period(years, "years")
    return present_value * (1 + annual_rate) ** years


def present_value(future_amount: float, annual_rate: float, years: float) -> float:
    """What a future amount is worth today: PV = FV / (1 + r)^n."""
    _check_rate(annual_rate)
    _check_period(years, "years")
    return future_amount / (1 + annual_rate) ** years


def inflate(amount_today: float, inflation_rate: float, years: float) -> float:
    """Cost of something in `years` time if prices rise by `inflation_rate` a year.

    Same formula as future_value; a separate name keeps goal code readable.
    """
    return future_value(amount_today, inflation_rate, years)


# --- SIPs (monthly instalments) ---------------------------------------------------------------


def _annuity_factor(i: float, months: int) -> float:
    """Future value of 1 rupee invested at the start of each month for `months` months.

    Sum of (1 + i)^k for k = 1..n  =  ((1 + i)^n - 1) / i * (1 + i). With i = 0 it is just n.
    """
    if i == 0:
        return float(months)
    return ((1 + i) ** months - 1) / i * (1 + i)


def sip_future_value(monthly_amount: float, annual_rate: float, months: int) -> float:
    """Value after `months` of a fixed SIP invested at the start of each month."""
    _check_period(months, "months")
    return monthly_amount * _annuity_factor(monthly_rate(annual_rate), months)


def step_up_sip_future_value(
    monthly_amount: float, annual_rate: float, years: int, step_up_rate: float
) -> float:
    """Value after `years` of a SIP that is raised by `step_up_rate` every year.

    Year k (k = 0..years-1) invests monthly_amount * (1 + s)^k each month for 12 months; that
    year's block then keeps growing for the remaining (years - 1 - k) years.
    """
    _check_period(years, "years")
    _check_rate(step_up_rate, "step-up rate")
    one_year_block = _annuity_factor(monthly_rate(annual_rate), MONTHS_PER_YEAR)
    return sum(
        monthly_amount
        * (1 + step_up_rate) ** k
        * one_year_block
        * (1 + annual_rate) ** (years - 1 - k)
        for k in range(years)
    )


def required_sip(
    target: float, annual_rate: float, months: int, current_savings: float = 0.0
) -> float:
    """Monthly SIP needed to reach `target`, after counting what current savings will grow to.

    Inverts sip_future_value: SIP = remaining / annuity_factor. Returns 0 when the savings
    alone are enough.
    """
    _check_period(months, "months")
    remaining = target - future_value(current_savings, annual_rate, months / MONTHS_PER_YEAR)
    if remaining <= 0:
        return 0.0
    if months == 0:
        raise FinanceInputError("the target date has already arrived")
    return remaining / _annuity_factor(monthly_rate(annual_rate), months)


def required_step_up_sip(
    target: float,
    annual_rate: float,
    years: int,
    step_up_rate: float,
    current_savings: float = 0.0,
) -> float:
    """Starting SIP needed when the SIP will be raised by `step_up_rate` every year.

    The step-up future value is proportional to the starting amount, so the answer is
    remaining / (future value of a step-up SIP that starts at 1 rupee).
    """
    remaining = target - future_value(current_savings, annual_rate, years)
    if remaining <= 0:
        return 0.0
    if years == 0:
        raise FinanceInputError("the target date has already arrived")
    return remaining / step_up_sip_future_value(1.0, annual_rate, years, step_up_rate)
