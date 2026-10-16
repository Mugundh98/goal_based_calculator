"""Peer groups: the SEBI category a fund competes in, from AMFI's inconsistent labels.

AMFI's NAV file names the same category differently from one fund house to the next ("Short
Term Fund", "Short Duration Fund"; "ELSS", "ELSS- Tax Saver Fund"). Ranking a fund only makes
sense against funds that try to do the same thing, so every label is mapped to one canonical
peer group by keyword rules, checked in order (the first match wins).

Index funds are a peer group of their own for clustering, but are not ranked: they track
different indices on purpose, so "top quartile" would only say which index rose most.
Generic labels from before SEBI's 2017 recategorisation ("Equity Funds", "Debt Funds",
"Income") cannot be placed and return None.
"""

import re

# (peer group, label shown to users, keywords - any one must occur in the lower-case category)
RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("index", "Index funds", ("index fund", "etf")),
    ("elss", "ELSS (tax saver)", ("elss", "tax saver")),
    ("large_mid_cap", "Large & mid cap", ("large & mid", "large and mid")),
    ("large_cap", "Large cap", ("large cap",)),
    ("mid_cap", "Mid cap", ("mid cap",)),
    ("small_cap", "Small cap", ("small cap",)),
    ("flexi_multi_cap", "Flexi & multi cap", ("flexi cap", "multi cap")),
    ("focused", "Focused", ("focused",)),
    ("value_contra", "Value, contra & dividend yield", ("value", "contra", "dividend yield")),
    ("sectoral_thematic", "Sectoral & thematic", ("sectoral", "thematic")),
    ("aggressive_hybrid", "Aggressive hybrid", ("aggressive hybrid", "balanced hybrid")),
    (
        "balanced_advantage",
        "Balanced advantage",
        ("balanced advantage", "dynamic asset allocation"),
    ),
    ("conservative_hybrid", "Conservative hybrid", ("conservative hybrid",)),
    ("multi_asset", "Multi asset", ("multi asset",)),
    ("equity_savings", "Equity savings", ("equity savings",)),
    ("arbitrage", "Arbitrage", ("arbitrage",)),
    ("overnight", "Overnight", ("overnight",)),
    ("liquid", "Liquid", ("liquid",)),
    ("money_market", "Money market", ("money market",)),
    ("low_duration", "Low duration", ("ultra short to short", "low duration")),
    ("ultra_short", "Ultra short duration", ("ultra short",)),
    ("short_duration", "Short duration", ("short term", "short duration")),
    ("medium_duration", "Medium & long duration", ("medium", "long term", "long duration")),
    ("dynamic_bond", "Dynamic bond", ("dynamic term", "dynamic bond")),
    ("corporate_bond", "Corporate bond", ("corporate bond",)),
    ("banking_psu", "Banking & PSU", ("banking and psu", "banking & psu")),
    ("gilt", "Gilt", ("gilt",)),
    ("credit_risk", "Credit risk", ("credit risk",)),
    ("floater", "Floater", ("floating", "floater")),
)

LABELS = {group: label for group, label, _ in RULES}
UNRANKED = frozenset({"index"})


def peer_group(category: str) -> str | None:
    text = re.sub(r"\s+", " ", category.lower())
    for group, _, keywords in RULES:
        if any(keyword in text for keyword in keywords):
            return group
    return None
