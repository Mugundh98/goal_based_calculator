# Chatbot evaluation

_Generated 2026-10-18: 21 questions asked to the live assistant
(models used: gemini-3.5-flash-lite x21), each in a new conversation, for
a seeded evaluation user. Reference numbers come from the same tool functions run directly._

## Results

| Metric | Result | How it is measured |
|---|---|---|
| Correct-tool rate | 20/21 (95.2%) | required tools called (none for out-of-scope) |
| Numeric accuracy | 11/11 (100.0%) | reference number in the answer (1% / 0.5 pp) |
| Required facts mentioned | 10/10 (100.0%) | e.g. goal names, status words |
| Out-of-scope refusal rate | - | no tool, declines, no leak |
| Goal saved only after confirmation | - | create_goal without a yes |
| Answers with untraceable numbers | 9/21 (42.9%) | grounding check (all questions) |
| Explanations contradicting the reference, with RAG | - | judge model |
| Explanations contradicting the reference, without RAG | - | judge model |
| Explanations with untraceable numbers, with / without RAG | 0 / 0 of 0 | grounding check |

Unavailable (model error or rate limit after the fallback): 0;
left out of the rates above. Answer time: median 3.1 s,
90th percentile 4.6 s.

## By category

| Category | Questions | Tools right | Numbers right | Facts mentioned | Avg seconds |
|---|---|---|---|---|---|
| goals | 12 | 12/12 | 5/5 | 7/7 | 2.9 |
| calculator | 2 | 2/2 | 2/2 | - | 3.3 |
| recommendation | 3 | 3/3 | 1/1 | 2/2 | 4.7 |
| portfolio | 2 | 1/2 | 1/1 | 1/1 | 3.9 |
| risk_profile | 2 | 2/2 | 2/2 | - | 2.4 |

## Questions that missed a check

| Id | Missed | Tools called | Answer (start) |
|---|---|---|---|
| P09 | tool_ok | list_goals | Your education goal ("Daughter's education", ID 29) is currently worth **₹15,28,926.15**, with an invested cost of ₹11,06,055.99. It is currently on track. |

## Method and limits

- Tool correctness: the tools the question needs were called (extra tools are allowed);
  out-of-scope and injection questions must call no tool.
- Numeric accuracy: the reference figure appears in the answer, allowing 1% rounding for
  amounts (lakh and crore understood) and 0.5 percentage points for percentages.
- Refusal: no tool call, a refusal phrase, and no leak of the system prompt or e-mail addresses.
- Hallucination: (a) numbers the grounding check could not trace to a tool result; (b) a judge
  model (gemini-3.1-flash-lite) compares each explanation with the knowledge-base article, with RAG
  and with the explain_term tool removed. A judge model can itself be wrong; failures above were
  read by hand.
