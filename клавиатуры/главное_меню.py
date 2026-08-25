"""Главное меню бота."""
# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def help_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Основное", callback_data="help_main"),
         InlineKeyboardButton("🎲 Игры", callback_data="help_games")],
        [InlineKeyboardButton("💥 Активности", callback_data="help_activities"),
         InlineKeyboardButton("💬 Чаты", callback_data="help_chats")],
    ])
