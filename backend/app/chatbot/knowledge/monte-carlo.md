# Monte Carlo simulation and the chance of success

## Why a single return is not enough

A plan that assumes 10% every year gives one answer, but markets do not deliver 10% every year. The order of good and bad years matters too: a crash just before the goal hurts far more than one at the start. A Monte Carlo simulation replaces the single assumed return with thousands of possible futures.

## How GoalWise simulates a goal

For each simulated path, GoalWise draws a sequence of monthly returns for the goal's mix of equity and debt, applies the savings and SIPs (with step-up), and checks whether the final value reaches the inflated target. The chance of success is the share of paths that reach it. The fan chart shows the range of outcomes each year: the middle 50% and the middle 80% of paths, the median path and the single-return plan.

## Return models

GoalWise offers four ways to generate returns. The normal model draws independent returns from a bell curve. The block bootstrap (the default) replays blocks of real Indian monthly returns, keeping fat tails and streaks. GARCH(1,1) lets volatility cluster, with calm and turbulent spells. A two-state hidden Markov model switches between a calm regime and a crisis regime. Comparing them shows how sensitive the answer is to the assumptions.

## Reading the results

A chance of success of 50% means the plan works in half of the futures. GoalWise also shows the SIP needed for a 50%, 75% and 90% chance, so the user can choose how much certainty to buy. Results come from models of the past and are estimates, not guarantees.
