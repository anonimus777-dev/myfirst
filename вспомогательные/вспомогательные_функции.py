# -*- coding: utf-8 -*-
import time
import html
from настройки import ROOMS_DATA, ROOM_BUY_PRICES, GAME_COOLDOWNS, MINE_CHANCES


def safe_nick(name: str) -> str:
    return html.escape(name)

def get_room_upgrade_cd(vip: int, levels: int) -> int:
    """Возвращает кулдаун в секундах для прокачки комнаты."""
    cd_map = {
        2: {20: 45},
        3: {20: 30, 100: 60},
        4: {20: 20, 100: 45, 1000: 120},
    }
    if vip not in cd_map:
        return 0
    return cd_map[vip].get(levels, 0)

# ── VIP water limits ───────────────────────────────────────────────────────────

def get_vip_water_limit(vip: int) -> int:
    return {0: 20, 1: 30, 2: 50, 3: 75, 4: 100}.get(vip, 20)

def get_vip_barrel_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 25, 4: 50}.get(vip, 1)

def get_vip_grow_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 15, 4: 20}.get(vip, 1)

def card_value(card):
    v = card[0]
    if v in ["J","Q","K"]:
        return 10
    if v == "A":
        return 11
    return int(v)

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def hand_str(hand):
    return " • ".join(f"{c[0]}{c[1]}" for c in hand)

def fmt_bottles(n: float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}kk"
    return f"{n:,.1f}"

def fmt_smart(n):
    try:
        n = float(n)
    except:
        return str(n)
    abs_n = abs(n)
    if abs_n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.2f}kkkk"
    if abs_n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}kkk"
    if abs_n >= 1_000_000:
        return f"{n/1_000_000:.2f}kk"
    return f"{int(n):,}".replace(",", ",")

fmt = fmt_smart

def parse_bet(s: str, balance: float) -> int:
    """Парсит ставку: число, 1k, 1kk, всё, all."""
    s = s.lower().strip()
    if s in ("всё", "все", "all"):
        return int(balance)
    try:
        if s.endswith("kkkk"):
            return int(float(s[:-4]) * 1_000_000_000_000)
        if s.endswith("kkk"):
            return int(float(s[:-3]) * 1_000_000_000)
        if s.endswith("kk"):
            return int(float(s[:-2]) * 1_000_000)
        if s.endswith("k"):
            return int(float(s[:-1]) * 1_000)
        return int(s)
    except:
        return -1

def user_link(user_id: int, name: str) -> str:
    """Обернуть имя игрока в кликабельную ссылку"""
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def get_upgrade_cost(room_num: int, current_level: int) -> int:
    coef = ROOMS_DATA[room_num]["coef"]
    current_income = get_current_income(room_num, current_level)
    return int(current_income * coef)

def get_current_income(room_num: int, level: int) -> int:
    base = ROOMS_DATA[room_num]["income"]
    inc = ROOMS_DATA[room_num]["inc_per_lvl"]
    return base + inc * (level - 1)

def get_balance_limit(rooms: list) -> int:
    base = 10000
    for r in rooms:
        if r["room_num"] == 5:
            base += r["level"] * 1000
    return base

def get_vip_transfer_limit(vip: int) -> int:
    limits = {0: 3000, 1: 5000, 2: 8000, 3: 15000, 4: 25000}
    return limits.get(vip, 3000)

def get_vip_level_name(vip: int) -> str:
    names = {0: "Нет", 1: "VIP1 ⚡️", 2: "VIP2 🔥", 3: "VIP3 💎", 4: "VIP4 ⭐️"}
    return names.get(vip, "Нет")

def get_mine_chances_by_depth(depth: int, pickaxe_idx: int) -> dict:
    """Возвращает шансы ресурсов в зависимости от глубины и кирки."""
    chances = {}
    # Песок
    if depth < 300:
        chances["sand"] = min(100, MINE_CHANCES["sand"][pickaxe_idx])
    # Уголь
    if depth < 40:
        coal_base = 0
    elif depth < 80:
        coal_base = 30
    elif depth < 150:
        coal_base = 60
    elif depth < 300:
        coal_base = 50
    else:
        coal_base = 40
    if coal_base > 0:
        chances["coal"] = min(coal_base, MINE_CHANCES["coal"][pickaxe_idx])
    # Железо
    if depth >= 80:
        iron_base = 20 if depth < 150 else (30 if depth < 300 else 40)
        chances["iron"] = min(iron_base, MINE_CHANCES["iron"][pickaxe_idx])
    # Медь
    if depth >= 150:
        copper_base = 30 if depth < 300 else 25
        chances["copper"] = min(copper_base, MINE_CHANCES["copper"][pickaxe_idx])
    # Серебро
    if depth >= 150:
        silver_base = 30 if depth < 300 else 35
        chances["silver"] = min(silver_base, MINE_CHANCES["silver"][pickaxe_idx])
    # Алмаз
    if depth >= 150:
        if depth < 200:
            diamond_base = 10
        elif depth < 300:
            diamond_base = 20
        elif depth < 400:
            diamond_base = 30
        else:
            diamond_base = 35
        chances["diamond"] = min(diamond_base, MINE_CHANCES["diamond"][pickaxe_idx])
    # Уран
    if depth >= 500:
        chances["uranium"] = min(20, MINE_CHANCES["uranium"][pickaxe_idx])
    return chances

def check_cooldown(uid: int) -> int:
    """Возвращает оставшиеся секунды КД, 0 если можно играть."""
    last = GAME_COOLDOWNS.get(uid, 0)
    diff = time.time() - last
    if diff < 3:
        return int(3 - diff) + 1
    return 0

def set_cooldown(uid: int):
    GAME_COOLDOWNS[uid] = time.time()
