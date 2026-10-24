# Literature Review

This chapter reviews the theory and prior work on which GoalWise is built. It moves from the economics of saving for goals, through portfolio theory and the measurement of fund performance, to the statistical models of market returns used in simulation, the use of machine learning to select funds, automated advisory systems, and finally the language-model techniques behind the conversational assistant. The last section surveys the tools available to Indian investors today and identifies the gap the project fills.

## Goal-based investing and mental accounting

Classical portfolio theory treats an investor's wealth as a single pool to be invested at one level of risk. Behavioural finance observed that real investors do not behave this way. Shefrin and Statman's behavioural portfolio theory [5] describes investors who divide their money into "mental accounts", each with its own purpose and its own attitude to risk: money for a child's education is treated differently from money for a holiday. Rather than dismissing this as irrational, Das, Markowitz, Scheid and Statman [4] showed that optimising each mental account separately, with a threshold return and a maximum acceptable probability of falling short, leads to portfolios that lie on the same mean-variance efficient frontier as the classical approach. Goal-based investing therefore loses little efficiency while gaining something investors value: a clear link between each sum of money and its purpose.

This insight shapes GoalWise directly. Each goal has its own target, horizon and SIP; each is simulated separately; and each receives its own asset allocation, more conservative as its date approaches. The probability of success that the simulation reports is the goal-based analogue of the "probability of falling short" in [4].

## Time value of money and inflation

The arithmetic of planning rests on the time value of money: a rupee today is worth more than a rupee in the future because it can be invested. Standard texts such as Bodie, Kane and Marcus [45] develop the present and future value of lump sums and annuities, the conversion between annual and monthly rates, and the effect of compounding. Fisher [31] distinguished nominal from real rates of return: with nominal return r and inflation π, the growth in purchasing power is (1 + r)/(1 + π) − 1, not simply r − π. Inflation matters greatly over long horizons; at 6% a year, prices double in about twelve years.

A SIP is an annuity due — each instalment is invested at the start of its month — and a SIP with a yearly increase is a growing annuity. Closed-form expressions exist for both, and GoalWise uses them for the deterministic plan of each goal (Chapter 5), checked against month-by-month simulation in its tests.

## Portfolio theory and asset allocation

Markowitz's mean-variance framework [1] showed that the risk of a portfolio depends on the covariances of its assets, not only their individual risks, and that for each level of risk there is a portfolio with the highest expected return: together these form the efficient frontier. The framework is elegant but sensitive to its inputs. Michaud [50] showed that unconstrained optimisation amplifies errors in estimated returns and produces extreme, unstable portfolios — "error maximisation". Practical systems therefore constrain the weights, use a small number of broad asset classes, and estimate inputs from long histories.

Asset allocation for a goal also depends on its horizon. The idea of a glide path, a share of equity that declines as the goal approaches, is the basis of target-date funds: a goal twenty years away can ride out several market falls, while a goal due next year cannot. GoalWise combines both ideas: a glide path sets bounds on equity from the goal's horizon and the user's risk profile, and a constrained mean-variance optimisation chooses the weights of four sleeves (large-cap equity, mid- and small-cap equity, long-duration debt and short-duration debt) within those bounds.

## Measuring fund performance

Sharpe [2] proposed measuring a fund by its excess return per unit of total risk, the ratio now named after him. Sortino and Price [3] argued that investors fear losses rather than volatility in general, and proposed dividing excess return by downside deviation alone. Maximum drawdown, the largest fall from a peak, describes the worst experience an investor would have had. GoalWise computes these measures, together with compound annual growth rates and rolling returns, for every fund with enough history.

Whether past performance predicts future performance is a long-standing question. Carhart [16] found that the persistence of mutual fund returns is largely explained by common factors, especially momentum, and by expenses, with little evidence of persistent skill except among the worst funds. Fama and French [17] concluded that few active funds earn enough to cover their costs once luck is accounted for. This literature sets a realistic expectation for any fund-selection model: beating a simple momentum rule ("buy last year's best funds within the category") is hard. GoalWise's machine-learning ranker is evaluated against exactly that baseline, and the result is reported honestly in Chapter 8.

## Monte Carlo simulation in financial planning

Monte Carlo methods estimate a quantity by averaging over many random samples. Glasserman [8] gives a thorough treatment of their use in finance, including variance reduction and the convergence of estimates: the standard error of an estimated probability p from N independent paths is √(p(1 − p)/N), so 10,000 paths estimate a 50% probability to within about half a percentage point.

In retirement planning, Bengen [6] used historical US returns to find the highest withdrawal rate that would have survived every 30-year period, the origin of the "4% rule". The Trinity study of Cooley, Hubbard and Walz [7] reported success rates for different withdrawal rates and asset mixes. Later work replaced historical sequences with simulation, which shows the full distribution of outcomes and the sequence-of-returns risk that a single average hides. GoalWise's retirement planner follows this approach, simulating the accumulation and drawdown phases together and reporting the probability that the money lasts to a chosen age.

## Models of market returns

The simplest model draws independent normal returns with a fixed mean and volatility. Real returns differ from this in three well-documented ways: their distribution has fat tails, their volatility clusters in time, and markets alternate between calm and turbulent regimes. Each of GoalWise's four return models addresses one of these.

**Bootstrap.** Efron's bootstrap [9] resamples observed data instead of assuming a distribution. Drawing single months independently keeps the fat tails but destroys the dependence between consecutive months. Künsch [10] introduced the block bootstrap, which resamples contiguous blocks and so preserves short-range dependence; Politis and Romano [11] proposed the circular variant, which wraps the series end to start so every observation has the same chance of selection. GoalWise draws 12-month circular blocks from Indian market history.

**Volatility clustering.** Engle's ARCH model [12] made the variance of today's return depend on yesterday's squared shock; Bollerslev's GARCH(1,1) [13] added dependence on yesterday's variance, giving a parsimonious model in which turbulent periods persist and then decay. GoalWise fits a GARCH(1,1) to monthly market returns.

**Regimes.** Hamilton [14] modelled economic time series as switching between unobserved states according to a Markov chain; Rabiner [47] gives the standard treatment of hidden Markov models and their estimation. A two-state model of "bull" and "bear" regimes, each with its own mean and volatility, reproduces long calm periods interrupted by crises. GoalWise fits such a model and simulates future regime sequences.

## Time-series forecasting of inflation

Box and Jenkins [15] established the ARIMA family of models for forecasting time series, with seasonal extensions (SARIMA) for monthly data such as consumer prices. GoalWise uses a SARIMA model on MOSPI's consumer price index to forecast inflation, which the application shows alongside the long-run assumption used in goal planning.

## Machine learning for fund selection

Gradient-boosted decision trees combine many shallow trees, each fitted to the errors of the previous ones. LightGBM [18] made the method fast on large data with histogram-based splitting and leaf-wise growth, and it is widely used for tabular prediction. Tree ensembles are accurate but opaque; Lundberg and Lee [19] introduced SHAP values, which attribute each prediction to its input features consistently with game-theoretic Shapley values. GoalWise uses LightGBM to predict a fund's quartile within its peer group over the next year from past-only features, and SHAP to show the main reasons behind each ranking.

Clustering groups funds by behaviour rather than by their declared category. The k-means algorithm [20] partitions observations into k groups by minimising within-group squared distance; Hastie, Tibshirani and Friedman [46] discuss its properties and the choice of k. GoalWise clusters funds on their risk and return characteristics and compares the result with a Gaussian mixture model.

A recurring danger in financial machine learning is look-ahead bias: using information that would not have been available at the time of the forecast. GoalWise avoids it by building every feature from data before the forecast date and by validating walk-forward, training on earlier years and testing on each following year in turn.

## Robo-advisory systems

Automated advisory services ("robo-advisers") emerged after 2008, offering portfolio construction and rebalancing through a web interface at low cost. Jung, Dorner, Glaser and Morana [29] describe their typical architecture: a questionnaire to profile the client, an allocation engine, and automated rebalancing. D'Acunto, Prabhala and Rossi [30] studied an Indian robo-adviser and found that it improved diversification for under-diversified investors, while noting that automated advice can amplify behavioural tendencies if it is not designed with care. In India, investment advice is regulated by SEBI's Investment Advisers Regulations [32]; tools that do not offer personalised advice must make clear that they are educational. SEBI's categorisation of mutual fund schemes [33] defines the categories (large cap, mid cap, corporate bond and so on) that GoalWise uses to form peer groups.

GoalWise shares the questionnaire and allocation structure of robo-advisers but differs in three respects: it works per goal rather than per portfolio, it reports probabilities rather than a single projection, and it explains its reasoning instead of presenting a finished portfolio.

## Language models, tools and retrieval

Large language models generate fluent text but can state false facts with confidence and are unreliable at arithmetic. Two techniques address this. In tool use, the model calls external functions and uses their results: ReAct [22] interleaves reasoning steps with actions, and Toolformer [23] showed that models can learn when to call tools such as calculators. In retrieval-augmented generation (RAG), proposed by Lewis et al. [21], relevant passages are retrieved from a document collection and given to the model with the question, grounding the answer in sources. Retrieval relies on vector embeddings and approximate nearest-neighbour search; the HNSW graph index of Malkov and Yashunin [24] is a common choice, and PostgreSQL's pgvector extension [41] provides it inside the database.

GoalWise's assistant applies both techniques: every number comes from a tool that runs the system's own calculations for the logged-in user, and explanations of financial concepts are grounded in a curated knowledge base retrieved by cosine similarity. A grounding check flags any number in an answer that does not appear in the tool results.

## Web architecture and security

The system follows the REST architectural style described by Fielding [25]: resources identified by URLs, manipulated through standard HTTP methods, with stateless requests. Authentication uses JSON Web Tokens [26], signed tokens that carry the user's identity and expire after a fixed time, so the server keeps no session state. Passwords are hashed with Argon2id [27], the winner of the Password Hashing Competition, which is deliberately slow and memory-hard to resist brute-force attacks. Usability is evaluated with the System Usability Scale of Brooke [28], a ten-item questionnaire scored from 0 to 100.

## Survey of existing tools

Table: Comparison of the kinds of tools available to Indian investors

| Kind of tool | Typical examples | What it offers | What it lacks |
| --- | --- | --- | --- |
| SIP and goal calculators | Calculators on fund-house, bank and media websites | A future value or required SIP at one assumed return | No uncertainty, usually no inflation or step-up, no link to real investments |
| Fund research websites | Rating and screening portals | Returns, ratings, risk measures, peer comparison | No link to a goal or horizon; ratings based on past returns only |
| Investment platforms and brokers | Direct mutual fund platforms, brokerage apps | Buying and selling, holdings, overall returns | No per-goal tracking against a plan, no probability of success |
| Robo-advisers | Automated portfolio services | Questionnaire, model portfolio, rebalancing | One portfolio rather than per goal; reasoning rarely explained |
| Human financial planners | SEBI-registered investment advisers | Personalised, holistic advice | Expensive; available to few |

The survey shows a gap: no widely available tool combines per-goal planning with inflation, a probability of success under realistic market models, data-driven fund selection with explanations, tracking of real investments against each goal, and plain-language explanation. GoalWise is designed to fill that gap, as an educational tool that makes the reasoning of a planner visible.

## Summary

The literature supports the main design choices of the project: planning goal by goal (mental accounting is efficient [4]); measuring uncertainty by simulation rather than a single projection [6, 8]; using several return models because real returns have fat tails, clustered volatility and regimes [10, 13, 14]; evaluating fund selection against a momentum baseline because persistence is weak [16, 17]; constraining optimisation because unconstrained mean-variance weights are unstable [50]; and grounding a language model with tools and retrieval because on its own it is unreliable with facts and figures [21, 22].
