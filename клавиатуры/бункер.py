"""Клавиатуры бункера и комнат."""
# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def room_keyboard(room_num: int, use_bottles: bool = False, vip: int = 0) -> InlineKeyboardMarkup:
    currency = "bottles" if use_bottles else "coins"
    currency_btn1 = InlineKeyboardButton("За 💰 [✅]" if not use_bottles else "За 💰", callback_data=f"room_currency_{room_num}_coins")
    currency_btn2 = InlineKeyboardButton("За 🍾 [✅]" if use_bottles else "За 🍾", callback_data=f"room_currency_{room_num}_bottles")
    rows = [
        [currency_btn1, currency_btn2],
        [InlineKeyboardButton("🔝 UP +1ур.", callback_data=f"room_up_{room_num}_1_{currency}"),
         InlineKeyboardButton("🔝 UP +5ур.", callback_data=f"room_up_{room_num}_5_{currency}")],
        [InlineKeyboardButton("🔝 UP +20ур.", callback_data=f"room_up_{room_num}_20_{currency}"),
         InlineKeyboardButton("🔝 UP +100ур.", callback_data=f"room_up_{room_num}_100_{currency}")],
        [InlineKeyboardButton("🔝 UP +1'000ур.", callback_data=f"room_up_{room_num}_1000_{currency}")],
        [InlineKeyboardButton("🔝 UP +5'000ур.", callback_data=f"room_up_{room_num}_5000_{currency}")],
    ]
    return InlineKeyboardMarkup(rows)


# TOP keyboards

def top_keyboard(current: str) -> InlineKeyboardMarkup:
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
    others = [c for c in all_cats if c[0] != current]
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
