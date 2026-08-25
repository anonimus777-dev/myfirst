"""Общие вспомогательные функции проекта."""

import html


def safe_nick(name: str) -> str:
    return html.escape(name)


def user_link(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{safe_nick(name)}</a>'


def fmt_smart(value: float | int) -> str:
    value = int(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}kkk".rstrip("0").rstrip(".")
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}kk".rstrip("0").rstrip(".")
    if value >= 1_000:
        return f"{value:,}".replace(",", ".")
    return str(value)


def fmt_bottles(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def parse_bet(raw: str, balance: float) -> int:
    value = raw.lower().replace(" ", "")
    if value in ("всё", "все", "all"):
        return int(balance)
    try:
        suffixes = (("kkkk", 1_000_000_000_000), ("kkk", 1_000_000_000), ("kk", 1_000_000), ("k", 1_000))
        for suffix, multiplier in suffixes:
            if value.endswith(suffix):
                return int(float(value[:-len(suffix)]) * multiplier)
        return int(value)
    except (ValueError, TypeError):
        return -1
