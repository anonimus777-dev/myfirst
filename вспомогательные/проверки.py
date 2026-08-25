"""Общие проверки доступа, состояния пользователя и игровых условий."""
# -*- coding: utf-8 -*-
import aiosqlite
from telegram import Update
from telegram.constants import ParseMode
from настройки import DB_PATH
from клавиатуры.общие import no_bunker_keyboard


async def require_bunker(update: Update) -> bool:
    uid = update.effective_user.id
    if not await user_exists(uid):
        kb = no_bunker_keyboard()
        text = "Сначала создайте Бункер чтобы пользоваться ботом с командой Создать бункер, либо по кнопке ниже"
        if update.message:
            await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return False
    return True

async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None

async def has_room(user_id: int, room_num: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM rooms WHERE user_id=? AND room_num=?", (user_id, room_num)
        ) as cur:
            return await cur.fetchone() is not None
