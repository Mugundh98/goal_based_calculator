# ADR-017: Portfolio entries from the user – their own NAV, funds not in the list, corrections

**Status:** Accepted · **Date:** 2026-10-21 · **Version:** 1.1.0 · **Amends:** ADR-012

## Context

After the deployment, the first round of user feedback asked for three things in the portfolio:

1. **Their own NAV.** Only about 1,500 of the 14,000 funds in the list have their full NAV history in the database (the Phase 4 backfill). An older purchase in any other fund could not be recorded, because GoalWise looked up the NAV of that day and found none. Users also have the exact NAV on their account statements.
2. **Funds that are not in the list**, such as a closed or merged scheme, a PMS, or a fund the user cannot find.
3. **Editing a transaction.** Phase 9 allowed only insert and delete (ADR-012). A correction was a delete plus a new entry.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Where the NAV comes from | Database only; **the user's, optional** | **Optional `nav` on a transaction; without it, the database's NAV of that day (or the week before)** | Historic transactions need no extra stored NAV history ("without burdening the database"). The default stays automatic. |
| Storing a fund the user adds | A separate table with its own holdings; **a `funds` row with an owner** | **`funds.owner_user_id`, no scheme code; a CHECK makes the two exclusive** | The FIFO ledger, holdings, XIRR, goal status and drift code work unchanged. Every public fund query (explorer, fund page, market stats, recommendation categories, pipeline lookup, admin count) filters `owner_user_id IS NULL`. |
| Valuing a fund with no market price | The user keeps a "current NAV" up to date; **at cost** | **At cost: value = FIFO cost of the units held** (the user's choice) | Never shows a made-up gain. XIRR for such a holding is about 0%, while realised gains from redemptions at the user's NAV still count. The UI says "valued at cost". |
| SIPs in a fund the user added | Ask for a NAV per instalment; **refuse** | **Refused, with a message: record each instalment as a purchase with its NAV** | A SIP is generated from stored NAVs, and there are none here. |
| Corrections | Keep delete + add; **edit in place** | **`PUT /api/portfolio/transactions/{id}`: the same validation as a new transaction; the old and new positions are rebuilt in one database transaction under the user's lock** | Easier for users with the same data guarantees. If the change would leave a later redemption without units, it is rolled back (`409`). The audit log records `portfolio.transaction.update` with the new values. |
| Deleting a user who has their own funds | Keep `RESTRICT` on `transactions.fund_id` and `holdings.fund_id`; **`NO ACTION`** | **`NO ACTION`** | `RESTRICT` is checked row by row while the cascade runs, so it could fail depending on the order of deletes. `NO ACTION` is checked at the end of the statement: a fund still in use can still never be deleted. A test deletes a user with their own fund. |

## Consequences

- Any past transaction can be recorded. With the NAV switch on, the database is not consulted for the price.
- A fund added by hand never appears to other users or in market features. Its holdings show "Added by you · valued at cost" and have no fund page.
- `transactions.nav` no longer always equals the database's NAV: it is the price the user actually got. That is closer to a real ledger.
- Migration `0013`; tests in `test_portfolio_api.py` (own NAV, a fund added by hand from creation to valuation, privacy, corrections, a rejected correction, deleting a user) and `TransactionForm.test.tsx`.
