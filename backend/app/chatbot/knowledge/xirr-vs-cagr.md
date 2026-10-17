# XIRR, CAGR and absolute return

## Absolute return

Absolute return is the simple gain as a percentage of what was invested: (current value − amount invested) ÷ amount invested. It ignores time, so 20% over one year and 20% over five years look the same.

## CAGR

The compound annual growth rate (CAGR) is the constant yearly rate that turns a starting value into an ending value over a number of years: (end ÷ start)^(1 ÷ years) − 1. It suits a single lump-sum investment held for a period, and it is how fund returns over 1, 3 and 5 years are usually reported.

## XIRR

XIRR (extended internal rate of return) handles many cash flows on different dates, such as SIP instalments, extra purchases and redemptions. It finds the yearly rate at which the present value of all the money put in equals the present value of all the money taken out plus today's value. Each instalment counts only for the time it was actually invested. For a single lump sum, XIRR and CAGR are the same.

## Why a SIP needs XIRR

Suppose ₹10,000 is invested every month for a year and the holding is worth ₹1,30,000 a month after the last instalment. The absolute gain is about 8.3%, but the money was invested on average for only about half a year, so the yearly return (XIRR) is close to 16%. Applying CAGR to the total invested would understate the return badly.

## How GoalWise calculates XIRR

GoalWise solves the XIRR equation with the Newton-Raphson method starting from 10% (as Excel does) and falls back to bisection if Newton's method fails. It does not show XIRR until the first investment is a year old, because annualising a few weeks of return exaggerates it.
