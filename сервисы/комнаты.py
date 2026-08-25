# -*- coding: utf-8 -*-
import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import ROOMS_DATA, ROOM_BUY_PRICES, DB_PATH, NUM_EMOJIS
from вспомогательные.вспомогательные_функции import fmt_smart, user_link
from вспомогательные.проверки import require_bunker, has_room
from вспомогательные.сообщения import build_room_text
from база_данных.база import get_user, get_rooms, get_room_level
from база_данных.бункер import do_room_upgrade
from клавиатуры.бункер import room_keyboard


async def cmd_room(update: Update, context: ContextTypes.DEFAULT_TYPE, room_num: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    vip = user.get("vip", 0)
    if room_num is None:
        await update.message.reply_text("Укажите номер комнаты, например: К 1")
        return
    if not await has_room(uid, room_num):
        await update.message.reply_text(f"{user_link(uid, user['username'])}, у тебя нет данной комнаты.\nТы можешь её купить командой: Купить комнату [номер комнаты].", parse_mode=ParseMode.HTML)
        return
    context.user_data[f"room_{room_num}_bottles"] = False
    text = await build_room_text(uid, room_num, use_bottles=False)
    if text:
        await update.message.reply_text(text, reply_markup=room_keyboard(room_num, use_bottles=False, vip=vip), parse_mode=ParseMode.HTML)

async def cmd_rooms_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    unlock = [
        (1, "со старта"), (2, "со старта"), (3, "со старта"), (4, "со старта"),
        (5, "от 5 🧍"), (6, "от 12 🧍"), (7, "от 24 🧍"), (8, "от 40 🧍"),
        (9, "от 80 🧍"), (10, "от 130 🧍"), (11, "от 220 🧍"), (12, "от 360 🧍"),
        (13, "от 500 🧍"), (14, "от 720 🧍"), (15, "от 1000 🧍"),
        (16, "от 1400 🧍"), (17, "от 2000 🧍"), (18, "от 3500 🧍"), (19, "от 5000 🧍"),
    ]
    lines = [f"🙎‍♂️ {user_link(user['user_id'], user['username'])}\n"]
    for rn, cond in unlock:
        emoji = NUM_EMOJIS.get(rn, f"{rn}.")
        lines.append(f"{emoji} {ROOMS_DATA[rn]['name']} - {cond}")
    lines.append("\nℹ️ Купить комнату можно командой - Купить комнату [номер]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def cmd_let_in(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    queue = user["queue"]
    if amount is None or amount <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, этой командой можно впустить людей в бункер!\nСледите за уровнями комнат!\n\nПример: Впустить [кол-во человек]", parse_mode=ParseMode.HTML)
        return
    if amount > queue:
        await update.message.reply_text(f"{user_link(uid, username)}, недостаточно людей, в очереди: {queue} чел.", parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET people = people + ?, queue = queue - ? WHERE user_id = ?",
            (amount, amount, uid)
        )
        await db.commit()
    user = await get_user(uid)
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты впустил(-а) {amount} человек(а) в бункер!"
    , parse_mode=ParseMode.HTML)

async def cmd_buy_room(update: Update, context: ContextTypes.DEFAULT_TYPE, room_num: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    rooms = await get_rooms(uid)
    owned = {r["room_num"] for r in rooms}

    if room_num is None:
        await update.message.reply_text(f"{user_link(uid, username)}, этой командой можно купить комнату!\nСписок комнат можно посмотреть командой Список комнат\n\nПример: Купить комнату [номер комнаты]", parse_mode=ParseMode.HTML)
        return

    if room_num < 5 or room_num > 19:
        await update.message.reply_text(f"{user_link(uid, username)}, можно купить комнаты с 5 по 19.", parse_mode=ParseMode.HTML)
        return

    if room_num in owned:
        await update.message.reply_text(f"{user_link(uid, username)}, у вас уже есть эта комната!", parse_mode=ParseMode.HTML)
        return

    req_people = ROOMS_DATA[room_num]["unlock_people"]
    if user["people"] < req_people:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно людей в бункере!", parse_mode=ParseMode.HTML)
        return

    price = ROOM_BUY_PRICES[room_num]

    if user["balance"] < price:
        await update.message.reply_text(
            f"{user_link(uid, username)}, недостаточно крышек!"
        , parse_mode=ParseMode.HTML)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, uid))
        await db.execute("INSERT INTO rooms (user_id, room_num, level) VALUES (?, ?, 1)", (uid, room_num))
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно купил(-а) комнату: {ROOMS_DATA[room_num]['name']}!\n"
    , parse_mode=ParseMode.HTML)

async def cmd_rooms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_rooms_list(update, context)
