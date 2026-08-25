"""Telegram-обработчики команд теплицы."""

import random
import aiosqlite
from telegram import Update
from telegram.constants import ParseMode

from настройки import DB_PATH
from база_данных.теплица import CROPS, ensure_greenhouse, get_available_crops, get_greenhouse
from вспомогательные.вспомогательные_функции import fmt_smart, user_link

CROP_FORMS = {
    "картошку": "картошка", "картошки": "картошка", "морковку": "морковь",
    "моркови": "морковь", "риса": "рис", "чеснока": "чеснок",
    "свеклу": "свекла", "свеклы": "свекла", "огурца": "огурец",
    "капусту": "капуста", "капусты": "капуста", "фасоли": "фасоль",
    "помидора": "помидор", "помидоры": "помидор", "баклажана": "баклажан",
}


def vip_water_limit(vip: int) -> int:
    return {0: 20, 1: 30, 2: 50, 3: 75, 4: 100}.get(vip, 20)


def vip_grow_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 15, 4: 20}.get(vip, 1)


def normalize_crop(raw: str) -> str:
    return CROP_FORMS.get(raw.lower(), raw.lower())


async def handle_my_greenhouse(update: Update, user: dict) -> None:
    user_id, name = user["user_id"], user["username"] or "Игрок"
    await ensure_greenhouse(user_id)
    greenhouse = await get_greenhouse(user_id)
    available = get_available_crops(greenhouse["exp"])
    selected = greenhouse["selected_crop"] if greenhouse["selected_crop"] in available else "картошка"
    stock = [
        f"  {data['emoji']} {crop.capitalize()} — {greenhouse.get(data['col'], 0)} шт."
        for crop, data in CROPS.items() if greenhouse.get(data["col"], 0)
    ]
    text = (
        f"🙎‍♂️ {user_link(user_id, name)}, информация о твоей теплице:\n"
        f"⭐ Опыт: {fmt_smart(greenhouse['exp'])}\n"
        f"💧 Вода: {greenhouse['water']}/{vip_water_limit(user.get('vip', 0))} л.\n"
        f"🪴 Выбранный сорт: {selected}\n\n📦 Твой склад:\n"
        + ("\n".join(stock) if stock else "  *пусто*")
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_greenhouse_info(update: Update, user: dict) -> None:
    lines = [f"{data['emoji']} {crop.capitalize()} — {fmt_smart(data['exp_req'])} опыта" for crop, data in CROPS.items()]
    await update.message.reply_text("🪴 Сорта теплицы:\n" + "\n".join(lines))


async def handle_greenhouse_rate(update: Update, user: dict) -> None:
    lines = [f"{data['emoji']} {crop.capitalize()} — {fmt_smart(data['sell_price'])} крышек/шт." for crop, data in CROPS.items()]
    await update.message.reply_text("📈 Курс теплицы:\n" + "\n".join(lines))


async def handle_grow(update: Update, user: dict, parts: list[str]) -> None:
    user_id, name, vip = user["user_id"], user["username"] or "Игрок", user.get("vip", 0)
    if len(parts) < 2:
        await update.message.reply_text("Пример: <code>Вырастить картошку 1</code>", parse_mode=ParseMode.HTML)
        return
    crop = normalize_crop(parts[1])
    if crop not in CROPS:
        await update.message.reply_text("Такого сорта нет.")
        return
    try:
        quantity = int(parts[2]) if len(parts) > 2 else 1
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, vip_grow_limit(vip)))
    await ensure_greenhouse(user_id)
    greenhouse = await get_greenhouse(user_id)
    data = CROPS[crop]
    if greenhouse["exp"] < data["exp_req"]:
        await update.message.reply_text(f"Нужно {fmt_smart(data['exp_req'])} опыта.")
        return
    if greenhouse["water"] < quantity:
        await update.message.reply_text("Недостаточно воды.")
        return
    harvest = sum(random.randint(1, 2) for _ in range(quantity))
    exp = sum(random.randint(1, 4) for _ in range(quantity))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE greenhouse SET {data['col']} = {data['col']} + ?, exp = exp + ?, water = water - ? WHERE user_id = ?",
            (harvest, exp, quantity, user_id),
        )
        await db.commit()
    await update.message.reply_text(f"{user_link(user_id, name)}, получено {harvest} {data['emoji']} и {exp} опыта.", parse_mode=ParseMode.HTML)


async def handle_sell_crop(update: Update, user: dict, parts: list[str]) -> bool:
    if len(parts) < 2:
        return False
    user_id, name = user["user_id"], user["username"] or "Игрок"
    crop = normalize_crop(parts[1])
    if crop not in CROPS:
        return False
    await ensure_greenhouse(user_id)
    greenhouse, data = await get_greenhouse(user_id), CROPS[crop]
    available = greenhouse.get(data["col"], 0)
    if not available:
        await update.message.reply_text(f"{user_link(user_id, name)}, у тебя нет {crop}.", parse_mode=ParseMode.HTML)
        return True
    try:
        quantity = available if len(parts) < 3 or parts[2].lower() in ("всё", "все") else int(parts[2])
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, available))
    income = quantity * data["sell_price"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE greenhouse SET {data['col']} = {data['col']} - ? WHERE user_id = ?", (quantity, user_id))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (income, user_id))
        await db.commit()
    await update.message.reply_text(f"Продано: {quantity} {data['emoji']} за {fmt_smart(income)} кр.")
    return True
