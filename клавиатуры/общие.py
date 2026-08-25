"""Общие и информационные клавиатуры."""
# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def no_bunker_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏗 Создать бункер", callback_data="create_bunker")]])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="help_back")]])

def donate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Купить 🪙 BBCoins", url="https://t.me/Alkyrin")],
        [InlineKeyboardButton("💰 Сайт для доната 💰", url="https://t.me/Alkyrin")],
    ])
