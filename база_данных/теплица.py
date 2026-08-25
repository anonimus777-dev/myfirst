# -*- coding: utf-8 -*-
import aiosqlite
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import DB_PATH, CROPS, CROP_FORMS, CROP_FORMS_ACC
from вспомогательные.вспомогательные_функции import (
    fmt_smart, user_link, get_vip_water_limit, get_vip_grow_limit,
)
from вспомогательные.проверки import require_bunker
from база_данных.база import get_user


async def get_greenhouse(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM greenhouse WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def ensure_greenhouse(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO greenhouse (user_id) VALUES (?)", (user_id,))
        await db.commit()

def get_available_crops(exp: int):
    return [name for name, data in CROPS.items() if data["exp_req"] <= exp]

async def handle_my_greenhouse(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_greenhouse(uid)
    gh = await get_greenhouse(uid)
    exp = gh["exp"]
    water = gh["water"]
    water_limit = get_vip_water_limit(vip)
    selected = gh["selected_crop"]
    available = get_available_crops(exp)
    if selected not in available:
        selected = "картошка"

    stock_lines = []
    for crop, data in CROPS.items():
        amount = gh.get(data["col"], 0)
        if amount > 0:
            stock_lines.append(f"   {data['emoji']} {crop.capitalize()} — {amount} шт.")
    stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"

    crop_emoji = CROPS[selected]["emoji"]
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, информация о твоей теплице:\n"
        f"  ⭐️ Опыт: {fmt_smart(exp)}\n"
        f"  💧 Вода: {water}/{water_limit} л.\n"
        f"  🪴 Тебе доступна: {selected}\n\n"
        f"📦 Твой склад:\n{stock_text}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔀 Выбрать сорт", callback_data=f"gh_select_{uid}")],
        [InlineKeyboardButton(f"💧 Вырастить {crop_emoji}", callback_data=f"gh_grow_{uid}_1")],
    ])
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_greenhouse_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды выращиваемых сортов:\n"
        f"   🥔 Картошка — доступна сразу\n"
        f"   🥕 Морковь — 500 опыта\n"
        f"   🍚 Рис — 2.000 опыта\n"
        f"   🧄 Чеснок — 5.000 опыта\n"
        f"   🍠 Свекла — 10.000 опыта\n"
        f"   🥒 Огурец — 25.000 опыта\n"
        f"   🥬 Капуста — 40.000 опыта\n"
        f"   🫘 Фасоль — 60.000 опыта\n"
        f"   🍅 Помидор — 100.000 опыта\n"
        f"   🍆 Баклажан — 125.000 опыта"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_greenhouse_rate(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды выращиваемых сортов и их цена:\n"
        f"   🥔 Картошка — 100 крышек/шт\n"
        f"   🥕 Морковь — 200 крышек/шт\n"
        f"   🍚 Рис — 600 крышек/шт\n"
        f"   🧄 Чеснок — 1,000 крышек/шт\n"
        f"   🍠 Свекла — 1,400 крышек/шт\n"
        f"   🥒 Огурец — 2,500 крышек/шт\n"
        f"   🥬 Капуста — 3,500 крышек/шт\n"
        f"   🫘 Фасоль — 5,000 крышек/шт\n"
        f"   🍅 Помидор — 10,000 крышек/шт\n"
        f"   🍆 Баклажан — 20,000 крышек/шт"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_grow(update: Update, user: dict, parts_raw: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_greenhouse(uid)
    gh = await get_greenhouse(uid)

    CROP_NAMES = list(CROPS.keys())
    if len(parts_raw) < 2:
        await update.effective_message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно вырастить определённый сорт!\n"
            f"Виды культур — {', '.join(CROP_NAMES)}\n\n"
            f"Пример: <code>Вырастить [название сорта] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return

    raw_crop = parts_raw[1].lower()
    crop_name = CROP_FORMS.get(raw_crop, raw_crop)
    if crop_name not in CROPS:
        await update.effective_message.reply_text(
            f"{user_link(uid, username)}, такого сорта нет! \n\nДоступны: {', '.join(CROP_NAMES)}",
            parse_mode=ParseMode.HTML
        )
        return

    crop_data = CROPS[crop_name]
    if gh["exp"] < crop_data["exp_req"]:
        await update.effective_message.reply_text(
            f"{user_link(uid, username)}, у тебя недостаточно опыта для выращивания {crop_name}!\n"
            f"Нужно: {fmt_smart(crop_data['exp_req'])} опыта",
            parse_mode=ParseMode.HTML
        )
        return

    max_qty = get_vip_grow_limit(vip)
    try:
        qty = int(parts_raw[2]) if len(parts_raw) >= 3 else 1
    except:
        qty = 1
    qty = max(1, min(qty, max_qty))

    water_limit = get_vip_water_limit(vip)
    water = gh["water"]
    if water < qty:
        # CallbackQuery.answer() does not parse HTML. Use plain username here.
        message = f"🙎‍♂️ {username}, у тебя недостаточно воды!"
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=False)
        else:
            await update.effective_message.reply_text(
                f"🙎‍♂️ {user_link(uid, username)}, у тебя недостаточно воды!",
                parse_mode=ParseMode.HTML
            )
        return

    total_crop = 0
    total_exp = 0
    for _ in range(qty):
        total_crop += random.randint(1, 2)
        total_exp += random.randint(1, 4)

    col = crop_data["col"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE greenhouse SET {col} = {col} + ?, exp = exp + ?, water = water - ? WHERE user_id=?",
            (total_crop, total_exp, qty, uid)
        )
        await db.commit()

    gh = await get_greenhouse(uid)
    water_left = gh["water"]
    message = (
        f"{username}, успешно выращено: {total_crop} {crop_data['emoji']}, "
        f"+{total_exp} опыта, -{qty} 💧"
    )
    if update.callback_query:
        await update.callback_query.answer(message, show_alert=False)
    else:
        await update.effective_message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, ты успешно вырастил(-а) {CROP_FORMS_ACC.get(crop_name, crop_name)}!\n"
            f"Получено: {total_crop} {crop_data['emoji']}, {total_exp} опыта\n"
            f"Потрачено: {qty} 💧\n"
            f"Осталось воды: {water_left}/{water_limit} 💧",
            parse_mode=ParseMode.HTML
        )

async def handle_sell_crop(update: Update, user: dict, parts_raw: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_greenhouse(uid)

    CROP_NAMES = list(CROPS.keys())
    if len(parts_raw) < 2:
        await update.effective_message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно продать плоды!\n"
            f"Курс — <code>Курс теплица</code>\n\n"
            f"Пример: <code>Продать [название] [кол-во или всё]</code>",
            parse_mode=ParseMode.HTML
        )
        return

    raw_crop = parts_raw[1].lower()
    crop_name = CROP_FORMS.get(raw_crop, raw_crop)
    if crop_name not in CROPS:
        return False

    gh = await get_greenhouse(uid)
    crop_data = CROPS[crop_name]
    col = crop_data["col"]
    available = gh.get(col, 0)

    if available <= 0:
        await update.effective_message.reply_text(
            f"{user_link(uid, username)}, у тебя нет {crop_name}!", parse_mode=ParseMode.HTML
        )
        return

    if len(parts_raw) >= 3:
        if parts_raw[2].lower() == "всё" or parts_raw[2].lower() == "все":
            qty = available
        else:
            try:
                qty = int(parts_raw[2])
            except:
                qty = 1
    else:
        qty = available

    qty = min(qty, available)
    earnings = qty * crop_data["sell_price"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE greenhouse SET {col} = {col} - ? WHERE user_id=?", (qty, uid)
        )
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (earnings, uid))
        await db.commit()

    await update.effective_message.reply_text(
        f"🙎‍♂️ {user_link(uid, username)}, ты продал(-а) {qty} {crop_data['emoji']} {crop_name} за {fmt_smart(earnings)} кр.!",
        parse_mode=ParseMode.HTML
    )


# ── Шахта ─────────────────────────────────────────────────────────────────────

async def water_refill_job(context: ContextTypes.DEFAULT_TYPE):
    """Добавляет 1 воду каждые 10 минут, не превышая лимит."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT vip FROM users WHERE user_id=?", (uid,)) as cur2:
                row = await cur2.fetchone()
            if not row:
                continue
            vip = row[0]
            water_limit = get_vip_water_limit(vip)
            await db.execute(
                "UPDATE greenhouse SET water = MIN(water + 1, ?) WHERE user_id=?",
                (water_limit, uid)
            )
        await db.commit()
