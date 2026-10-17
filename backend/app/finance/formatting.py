"""Rupee amounts as Indians write them: ₹8,74,512 and ₹12.5 lakh. Pure functions."""


def inr(amount: float, symbol: str = "₹") -> str:
    """Indian digit grouping: the last three digits, then pairs (₹1,23,45,678)."""
    digits = str(abs(round(amount)))
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        head, pair = head[:-2], head[-2:]
        pairs.insert(0, pair)
    grouped = ",".join(([head] if head else []) + pairs + [tail])
    return f"{'−' if amount < 0 else ''}{symbol}{grouped}"


def lakh_crore(amount: float, symbol: str = "₹") -> str:
    """₹12.50 lakh, ₹1.20 crore; smaller amounts in full."""
    size = abs(amount)
    if size >= 1e7:
        return f"{symbol}{amount / 1e7:.2f} crore"
    if size >= 1e5:
        return f"{symbol}{amount / 1e5:.2f} lakh"
    return inr(amount, symbol)
