"""Number and date formatting shared by the terminal summary and the card."""
from __future__ import annotations

from datetime import date


def compact(n: float) -> str:
    """2_040_000_000 -> '2.04B', 192_000_000 -> '192M', 12_340 -> '12.3K', 999_999 -> '1M', 950 -> '950'."""
    value = float(n)
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= size * 0.9995:  # 999,999 rounds up to 1M rather than showing as 1000K
            scaled = value / size
            text = f"{scaled:.2f}" if scaled < 9.995 else f"{scaled:.1f}" if scaled < 99.95 else f"{scaled:.0f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return text + unit
    return f"{int(round(value)):,}"


def grouped(n: float) -> str:
    return f"{int(round(n)):,}"


def money(usd: float) -> str:
    return f"${usd:,.0f}" if usd >= 100 else f"${usd:,.2f}"


def percent(share: float) -> str:
    return f"{round(share * 100)}%"


def day_label(iso_day: str) -> str:
    """'2026-03-14' -> 'Mar 14'."""
    d = date.fromisoformat(iso_day)
    return f"{d.strftime('%b')} {d.day}"


def hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


def hours_text(hours: float) -> str:
    if hours < 1:
        return f"{round(hours * 60)}m"
    return f"{hours:,.0f}h" if hours >= 10 else f"{hours:.1f}h"
