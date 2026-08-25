# -*- coding: utf-8 -*-
import aiosqlite
import random
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import DB_PATH, ROOMS_DATA, ROOM_BUY_PRICES, ROOM_UPGRADE_COOLDOWNS
from вспомогательные.вспомогательные_функции import (
    get_upgrade_cost, get_current_income, get_room_upgrade_cd, user_link, fmt_smart,
    fmt_bottles, get_balance_limit,
)
from вспомогательные.проверки import has_room
from база_данных.база import get_user, get_rooms, get_room_level, get_total_income


async def do_room_upgrade(user_id: int, room_num: int, levels: int, use_bottles: bool) -> str:
    user = await get_user(user_id)
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)

    vip_requirements = {20: 1, 100: 2, 1000: 3, 5000: 4}
    required_vip = vip_requirements.get(levels, 0)
    if required_vip > 0 and vip < required_vip:
        vip_names = {1: "VIP1", 2: "VIP2", 3: "VIP3", 4: "VIP4"}
        return f"Эта функция доступна только для обладателей статуса {vip_names[required_vip]} и выше!"

    if not await has_room(user_id, room_num):
        return f"{user_link(user_id, username)}, у вас нет комнаты №{room_num}."

    current_level = await get_room_level(user_id, room_num)
    balance = user["balance"]
    bottles = user["bottles"]

    BOTTLE_TO_COINS = 10000

    total_cost = sum(get_upgrade_cost(room_num, current_level + i) for i in range(levels))

    if use_bottles:
        total_cost_bottles = total_cost / BOTTLE_TO_COINS
        if bottles < total_cost_bottles:
            return f"Недостаточно бутылок! Нужно {fmt_bottles(total_cost_bottles)} 🍾."
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bottles = bottles - ? WHERE user_id = ?", (total_cost_bottles, user_id))
            await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?",
                             (levels, user_id, room_num))
            await db.commit()
    else:
        if balance < total_cost:
            return f"Недостаточно крышек! Нужно {fmt_smart(total_cost)} кр."
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
            await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?",
                             (levels, user_id, room_num))
            await db.commit()

    new_level = current_level + levels
    new_income = get_current_income(room_num, new_level)

    # Шанс поломки бункера
    break_chances = {1: 1, 5: 3, 20: 10, 100: 15, 1000: 25, 5000: 25}
    break_chance = break_chances.get(levels, 0)
    broke = random.randint(1, 100) <= break_chance

    cost_text = f"{fmt_bottles(total_cost / BOTTLE_TO_COINS)} 🍾" if use_bottles else f"{fmt_smart(total_cost)} кр."

    if broke:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bunker_broken = 1 WHERE user_id=?", (user_id,))
            await db.commit()
        return f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня за {cost_text}.", True

    return (
        f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня\n"
        f"за {cost_text}."
    ), False

async def queue_refill_job(context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE queue < 5") as cur:
            users = await cur.fetchall()
        for (uid,) in users:
            radio_level = 0
            async with db.execute("SELECT level FROM rooms WHERE user_id=? AND room_num=8", (uid,)) as cur2:
                row = await cur2.fetchone()
                if row:
                    radio_level = row[0]
            chance = 0.55 + radio_level * 0.005
            if random.random() < chance:
                await db.execute("UPDATE users SET queue = MIN(queue + 1, 5) WHERE user_id = ?", (uid,))
        await db.commit()


# ── Rating handlers ──────────────────────────────────────────────────────────

async def passive_income_job(context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT room_num, level FROM rooms WHERE user_id=?", (uid,)) as cur2:
                rooms = await cur2.fetchall()
            if not rooms:
                continue
            rooms_list = [{"room_num": r[0], "level": r[1]} for r in rooms]
            half_income = sum(get_current_income(r["room_num"], r["level"]) for r in rooms_list) // 2
            if half_income <= 0:
                continue
            limit = get_balance_limit(rooms_list)
            async with db.execute("SELECT balance, bunker_broken FROM users WHERE user_id=?", (uid,)) as cur3:
                row = await cur3.fetchone()
            if not row:
                continue
            current, broken = row[0], row[1] or 0
            half_income = sum(get_current_income(r["room_num"], r["level"]) for r in rooms_list) // 2
            if broken:
                half_income = half_income // 2
            # Проверяем бензин
            async with db.execute("SELECT fuel FROM users WHERE user_id=?", (uid,)) as cur_f:
                fuel_row = await cur_f.fetchone()
            has_fuel = fuel_row and fuel_row[0] > 0
            if not has_fuel:
                continue  # Нет бензина — нет дохода
            add = min(half_income, max(0, limit - current))
            if add > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id=?",
                    (add, uid)
                )
        await db.commit()
# ── Бочки ─────────────────────────────────────────────────────────────────────

async def handle_repair_bunker(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    broken = user.get("bunker_broken", 0)
    if not broken:
        await update.message.reply_text(
            f"{user_link(uid, username)}, твой бункер в порядке, ничего чинить не нужно!",
            parse_mode=ParseMode.HTML
        )
        return
    total_income = await get_total_income(uid)
    repair_cost = int(total_income * 0.20)
    if user["balance"] < repair_cost:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя недостаточно крышек для починки бункера!\n"
            f"Необходимо: {fmt_smart(repair_cost)} кр.",
            parse_mode=ParseMode.HTML
        )
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ?, bunker_broken = 0 WHERE user_id=?",
                         (repair_cost, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно исправил(-а) происшествие в бункере за {fmt_smart(repair_cost)} кр.!",
        parse_mode=ParseMode.HTML
    )


# ── Теплица ───────────────────────────────────────────────────────────────────
