"""Клавиатуры бункера и комнат."""
# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def room_keyboard(room_num: int, use_bottles: bool = False, vip: int = 0) -> InlineKeyboardMarkup:
    currency_btn1 = InlineKeyboardButton("За 💰 [✅]" if not use_bottles else "За 💰", callback_data=f"room_currency_{room_num}_coins")
    currency_btn2 = InlineKeyboardButton("За 🍾 [✅]" if use_bottles else "За 🍾", callback_data=f"room_currency_{room_num}_bottles")
    rows = [
        [currency_btn1, currency_btn2],
        [InlineKeyboardButton("🔝 UP +1ур.", callback_data=f"room_up_{room_num}_1"),
         InlineKeyboardButton("🔝 UP +5ур.", callback_data=f"room_up_{room_num}_5")],
        [InlineKeyboardButton("🔝 UP +20ур.", callback_data=f"room_up_{room_num}_20"),
         InlineKeyboardButton("🔝 UP +100ур.", callback_data=f"room_up_{room_num}_100")],
        [InlineKeyboardButton("🔝 UP +1'000ур.", callback_data=f"room_up_{room_num}_1000")],
        [InlineKeyboardButton("🔝 UP +5'000ур.", callback_data=f"room_up_{room_num}_5000")],
    ]
    return InlineKeyboardMarkup(rows)


# TOP keyboards

def top_keyboard(current: str) -> InlineKeyboardMarkup:
    """
    Returns inline keyboard for /top with current category excluded (moved to its position).
    Categories: rating, income, coins, greenhouse, wasteland, guilds, residents, bottles
    Layout when 'rating' is current:
      Row1: 💵 Доход | 💰 Крышки
      Row2: ⭐️ Теплица | 🏜 Пустошь
      Row3: 🏰 Гильдии | 🧍 Жители
      Row4: 🍾 Бутылки
    """
    all_cats = [
        ("rating",    "🏆 Рейтинг"),
        ("income",    "💵 Доход"),
        ("coins",     "💰 Крышки"),
        ("greenhouse","⭐️ Теплица"),
        ("wasteland", "🏜 Пустошь"),
        ("guilds",    "🏰 Гильдии"),
        ("residents", "🧍 Жители"),
        ("bottles",   "🍾 Бутылки"),
    ]
    # Remove current from list, put it first
    others = [c for c in all_cats if c[0] != current]
    # bottles always last row alone
    bottles_cat = next((c for c in others if c[0] == "bottles"), None)
    non_bottles = [c for c in others if c[0] != "bottles"]

    rows = []
    for i in range(0, len(non_bottles), 2):
        row = []
        for cat in non_bottles[i:i+2]:
            row.append(InlineKeyboardButton(cat[1], callback_data=f"top_{cat[0]}"))
        rows.append(row)
    if bottles_cat:
        rows.append([InlineKeyboardButton(bottles_cat[1], callback_data=f"top_{bottles_cat[0]}")])
    return InlineKeyboardMarkup(rows)
