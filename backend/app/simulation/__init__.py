"""Monte Carlo simulation of goals: thousands of possible futures instead of one assumed return.

Pure code only - NumPy, no database, no HTTP - like `app/finance`:

* `allocation.py` - the link between an equity share and an assumed return.
* `history.py` - turns monthly equity and debt returns into a portfolio's return history.
* `models.py` - four return models (normal, block bootstrap, GARCH(1,1), 2-state HMM).
* `engine.py` - the vectorised engine: paths, success probability, percentile bands.
* `benchmark.py` - timing of the vectorised engine against plain Python loops.

Conventions are the Phase 3 ones (ADR-006) plus ADR-008: the expected return is the MEDIAN
(compound) growth rate, so a simulation with zero volatility reproduces the Phase 3 projection.
"""
