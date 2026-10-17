# How GoalWise ranks funds, and how far to trust it

## What the model predicts

GoalWise's fund model is a LightGBM ranker trained on monthly data of direct growth funds. For each fund and month it predicts which quartile of its SEBI peer group the fund will be in over the next 12 months (top quartile = best 25% of returns). It uses only information available at that time: past returns over several horizons, volatility and downside volatility, worst fall, Sharpe ratio, beta, alpha and correlation against the Nifty 500, the fund's age, how it compares with its peer group, and the state of the market.

## How it was tested

The model was tested with walk-forward validation: trained on data up to a point, tested on the following years it had never seen, with a gap so that no 12-month target overlaps the training data. It was compared with a momentum baseline (simply ranking by last year's return) and with random picks. Its rank correlation with actual outcomes was about 0.25, close to momentum, and 36% of its top picks landed in the top quartile against 25% by chance.

## What this means for investors

Past performance is a weak guide to future performance; the model's edge is modest and comparable to following momentum. Rankings are useful to narrow choices within a category and to avoid consistently weak funds, not to chase last year's winner. Spreading money across a few good funds from different fund houses, keeping costs low and reviewing once a year matter more.

## Explanations

For each ranked fund, GoalWise shows the factors that pushed the prediction up or down, computed exactly from the trees (SHAP values), so the reasons behind a ranking can be checked.
