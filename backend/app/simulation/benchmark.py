"""Time the vectorised engine against plain Python loops (for the report and the viva).

    uv run python -m app.simulation.benchmark [paths] [years]

Both versions use the same random shocks and must give the same final values.
"""

import sys
import time

import numpy as np

from app.finance.goal_plan import GoalInputs
from app.simulation import engine
from app.simulation.models import NormalModel

# The Phase 3 worked example: Ananya's engineering degree.
EXAMPLE = GoalInputs(
    target_today=2_000_000,
    years=15,
    inflation_rate=0.10,
    expected_return=0.12,
    current_savings=200_000,
    monthly_sip=15_000,
)
EXAMPLE_SIGMA = 0.15 / 12**0.5  # 15% a year


def main(paths: int = engine.DEFAULT_PATHS, years: int = EXAMPLE.years) -> None:
    goal = GoalInputs(**{**EXAMPLE.__dict__, "years": years})
    months = years * 12
    shocks = NormalModel(EXAMPLE_SIGMA).shocks(np.random.default_rng(1), paths, months)
    log_returns = shocks + np.log1p(goal.expected_return) / 12

    start = time.perf_counter()
    looped = engine.final_values_loop(
        log_returns, goal.current_savings, goal.monthly_sip, goal.step_up_rate
    )
    loop_seconds = time.perf_counter() - start

    start = time.perf_counter()
    growth, per_rupee = engine.year_end_components(log_returns, goal.step_up_rate)
    vectorised = goal.current_savings * growth[:, -1] + goal.monthly_sip * per_rupee[:, -1]
    vector_seconds = time.perf_counter() - start

    start = time.perf_counter()
    engine.run(goal, NormalModel(EXAMPLE_SIGMA), paths=paths)
    full_seconds = time.perf_counter() - start

    difference = float(np.max(np.abs(np.asarray(looped) - vectorised)))
    print(f"{paths:,} paths x {months} months = {paths * months:,} path-months")
    print(f"Python loops:        {loop_seconds * 1000:9.1f} ms")
    speed_up = loop_seconds / vector_seconds
    print(f"NumPy vectorised:    {vector_seconds * 1000:9.1f} ms  ({speed_up:.0f}x faster)")
    print(f"Full engine.run():   {full_seconds * 1000:9.1f} ms  (incl. random draws, percentiles)")
    print(f"Largest difference between the two: Rs {difference:.6f}")


if __name__ == "__main__":
    main(*(int(arg) for arg in sys.argv[1:3]))
