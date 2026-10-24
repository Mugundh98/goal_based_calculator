# Conclusion, Limitations and Future Research

## Conclusion

This project set out to build a system that plans each financial goal separately, measures the chance of reaching it under realistic market behaviour, recommends investments from real data, tracks actual investments against the plan, and explains everything in plain language. GoalWise does this. It combines the mathematics of the time value of money, Monte Carlo simulation under four statistical models of market returns, machine-learning models trained and validated on Indian mutual fund data, constrained portfolio optimisation, portfolio accounting with XIRR and a grounded conversational assistant in a single web application. The application is tested by 684 automated tests that run on every change and is deployed for use at no cost.

The work shows that the central weakness of common planning tools — a single projected number — can be replaced by a probability and a range without making the tool harder to use, and that the difference matters: the "required" SIP of a deterministic plan succeeds only about half the time. It also shows the value of evaluating each intelligent component honestly against simple baselines, and of constraining a language model with tools and retrieval so that it explains rather than invents.

## Limitations

1. **Historical data.** The simulations learn the shape of market risk from about 14 years of Indian history. A future unlike that period — a prolonged crisis, a change of regime, much higher inflation — is not represented. The expected return is an assumption chosen by the user or derived from the risk profile, not a forecast.
2. **Fund ranking accuracy.** The ranker does not beat a simple momentum baseline. Fund performance is hard to predict from public data, and the rankings should be read as an explained comparison within peers.
3. **Asset coverage.** Only mutual funds are modelled. Direct equities, bonds, gold, real estate, insurance, provident funds and international investments are not separate asset classes, and taxes on income and capital gains are not computed.
4. **Correlated goals.** Each goal is simulated on its own. In reality all of a household's goals share one market, and a bad decade hurts them all at once.
5. **Dependence on external services.** The assistant needs an external language model with free-tier rate limits and an internet connection, and the free hosting sleeps when idle and runs one simulation at a time; the deployment suits demonstration rather than many simultaneous users.
6. **Account recovery.** Without e-mail, forgotten passwords are reset with a security question, which is weaker than a link sent to a verified address.
7. **User evaluation.** The usability test kit is complete, but the sample of participants is small by design, so the results describe usability rather than measure behaviour change.
8. **Not regulated advice.** The system is an educational planning tool. It does not know a user's complete financial situation and does not provide personalised advice under SEBI's regulations.

## Guidelines for future research

1. **Household-level simulation.** Simulate all goals on the same market paths and add rules for priorities when money falls short, so that the probability of meeting *all* essential goals can be reported.
2. **Wider asset classes and taxes.** Add gold, international equity, fixed deposits and provident funds, and model after-tax returns, including long-term capital gains and tax-loss harvesting.
3. **Better fund selection.** Add expense ratios, portfolio holdings, manager tenure and style data, and test rigorously whether any combination beats the momentum baseline out of sample. Investigate ranking objectives (learning to rank) rather than quartile classification.
4. **Forward-looking return assumptions.** Combine historical risk with forward-looking estimates such as valuation-based equity returns and current bond yields, and study how sensitive the plans are to these assumptions.
5. **Automatic data import.** Import holdings from consolidated account statements instead of manual entry, reducing effort and errors.
6. **Behavioural research.** Run controlled studies of whether showing probabilities and ranges, instead of single numbers, changes how much and how consistently people save.
7. **Multilingual assistant.** Extend the assistant and its evaluation set to Indian languages, with knowledge-base articles in each language.
8. **Stronger account security.** Add e-mail verification and reset links, and token revocation on password change.
9. **Scalability.** Move simulations to a background worker with a queue, use paid hosting with more memory, and cache results, so that many users can be served at once.

GoalWise provides a tested, documented foundation on which each of these directions can be explored.
