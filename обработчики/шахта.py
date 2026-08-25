"""Telegram-обработчики шахты."""

import random
import aiosqlite
from telegram import Update
from telegram.constants import ParseMode

from настройки import DB_PATH
from база_данных.шахта import PICKAXES, MINE_CHANCES, MINE_RESOURCES, ensure_mine, get_mine
from вспомогательные.вспомогательные_функции import fmt_smart, user_link


async def handle_my_mine(update: Update, user: dict) -> None:
    await ensure_mine(user["user_id"])
    mine = await get_mine(user["user_id"])
    pickaxe = PICKAXES.get(mine["pickaxe"])
    resources = [
        f"{data['emoji']} {data['name']} — {mine.get(resource, 0)}"
        for resource, data in MINE_RESOURCES.items() if mine.get(resource, 0)
    ]
    text = (
        f"🚂 {user_link(user['user_id'], user['username'] or 'Игрок')}, твоя шахта:\n"
        f"Глубина: {mine['depth']} м\n"
        f"Кирка: {pickaxe['name'] if pickaxe else 'нет'}\n"
        f"Прочность: {mine['durability']}\n\n"
        f"Ресурсы:\n" + ("\n".join(resources) if resources else "пусто")
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_mine_info(update: Update, user: dict) -> None:
    lines = [f"{idx}. {data['emoji']} {data['name']} — {fmt_smart(data['price'])} кр., прочность {data['durability']}" for idx, data in PICKAXES.items()]
    await update.message.reply_text("⛏ Кирки:\n" + "\n".join(lines))


async def handle_mine_rate(update: Update, user: dict) -> None:
    lines = [f"{data['emoji']} {data['name']} — {fmt_smart(data['sell'])} кр." for data in MINE_RESOURCES.values()]
    await update.message.reply_text("📈 Курс шахты:\n" + "\n".join(lines))


async def handle_buy_pickaxe(update: Update, user: dict, pickaxe_num: int) -> None:
    if pickaxe_num not in PICKAXES:
        await update.message.reply_text("Номер кирки: от 1 до 3.")
        return
    pickaxe = PICKAXES[pickaxe_num]
    if user["balance"] < pickaxe["price"]:
        await update.message.reply_text("Недостаточно крышек.")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (pickaxe["price"], user["user_id"]))
        await db.execute("INSERT OR IGNORE INTO mine (user_id) VALUES (?)", (user["user_id"],))
        await db.execute("UPDATE mine SET pickaxe = ?, durability = ? WHERE user_id = ?", (pickaxe_num, pickaxe["durability"], user["user_id"]))
        await db.commit()
    await update.message.reply_text(f"Куплена {pickaxe['name']}.")


async def handle_dig(update: Update, user: dict) -> None:
    user_id = user["user_id"]
    await ensure_mine(user_id)
    mine = await get_mine(user_id)
    if not mine["pickaxe"] or mine["durability"] <= 0:
        await update.message.reply_text("Купи кирку: <code>Купить кирку 1</code>.", parse_mode=ParseMode.HTML)
        return
    pickaxe_index = mine["pickaxe"] - 1
    allowed = [key for key, chance in MINE_CHANCES.items() if chance[pickaxe_index] > 0]
    weights = [MINE_CHANCES[key][pickaxe_index] for key in allowed]
    resource = random.choices(allowed, weights=weights, k=1)[0]
    gained = random.randint(1, 3)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE mine SET {resource} = {resource} + ?, durability = durability - 1, depth = depth + 1 WHERE user_id = ?", (gained, user_id))
        await db.commit()
    data = MINE_RESOURCES[resource]
    await update.message.reply_text(f"⛏ Добыто: {gained} {data['emoji']} {data['name']}.")


async def handle_sell_mine_resource(update: Update, user: dict, resource: str, quantity_raw: str) -> bool:
    if resource not in MINE_RESOURCES:
        return False
    await ensure_mine(user["user_id"])
    mine = await get_mine(user["user_id"])
    available = mine.get(resource, 0)
    if not available:
        await update.message.reply_text("Этого ресурса нет на складе.")
        return True
    try:
        quantity = available if quantity_raw.lower() in ("всё", "все") else int(quantity_raw)
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, available))
    income = quantity * MINE_RESOURCES[resource]["sell"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE mine SET {resource} = {resource} - ? WHERE user_id = ?", (quantity, user["user_id"]))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (income, user["user_id"]))
        await db.commit()
    await update.message.reply_text(f"Продано за {fmt_smart(income)} кр.")
    return True
