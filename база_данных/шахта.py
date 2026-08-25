# -*- coding: utf-8 -*-
import aiosqlite
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from настройки import DB_PATH, PICKAXES, MINE_RESOURCES, MINE_CHANCES
from вспомогательные.вспомогательные_функции import fmt_smart, user_link, get_mine_chances_by_depth
from вспомогательные.проверки import require_bunker, has_room
from база_данных.база import get_user


async def get_mine(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM mine WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def ensure_mine(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO mine (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def handle_mine_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот доступные кирки:\n\n"
        f"  ⛏️ Каменная кирка — 30,000 крышек\n"
        f"      Запас прочности — 1\n"
        f"  ⛏️ Железная кирка — 200,000 крышек\n"
        f"      Запас прочности — 3\n"
        f"  💎 Алмазная кирка — 1,000,000 крышек\n"
        f"      Запас прочности — 5\n\n"
        f"Ресурсы и шансы на их добычу:\n"
        f"  🏜️ Песок — 100/100/100%\n"
        f"  ◾️ Уголь — 85/100/100%\n"
        f"  🚂 Железо — 50/90/100%\n"
        f"  🟠 Медь — 30/50/80%\n"
        f"  🥈 Серебро — 0/40/70%\n"
        f"  💎 Алмаз — 0/30/60%\n"
        f"  ☢️ Уран — 0/10/40%\n\n"
        f"Купить кирку: <code>Купить кирку [1/2/3]</code>\n"
        f"Курс: <code>Курс шахта</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_my_mine(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, у тебя нет шахты!\nНужна комната 12.",
            parse_mode=ParseMode.HTML
        )
        return
    await ensure_mine(uid)
    m = await get_mine(uid)
    pickaxe_id = m["pickaxe"]
    if pickaxe_id == 0:
        pickaxe_name = "Нет кирки"
    else:
        pickaxe_name = PICKAXES[pickaxe_id]["name"]
    durability = m["durability"]
    depth = m["depth"]

    stock_lines = []
    for key, res in MINE_RESOURCES.items():
        amount = m.get(res["col"], 0)
        if amount > 0:
            stock_lines.append(f"   {res['emoji']} {res['name']} — {amount} кг.")
    stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"

    text = (
        f"🙎‍♂️ {user_link(uid, username)}, информация о твоей шахте:\n"
        f"  ⛏️ Кирка: {pickaxe_name}\n"
        f"  ⚙️ Прочность: {durability}\n"
        f"  📉 Уровень погружения: {depth} м.\n\n"
        f"📦 Твой склад:\n{stock_text}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ Копать", switch_inline_query_current_chat="Копать")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_mine_rate(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды ресурсов и их цена:\n"
        f"   🏜️ Песок — 2,000 кр/кг\n"
        f"   ◾️ Уголь — 5,000 кр/кг\n"
        f"   🚂 Железо — 8,000 кр/кг\n"
        f"   🟠 Медь — 12,000 кр/кг\n"
        f"   🥈 Серебро — 18,000 кр/кг\n"
        f"   💎 Алмаз — 60,000 кр/кг\n"
        f"   ☢️ Уран — 150,000 кр/кг"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

DIG_PENDING = {}  # uid -> {"resource": key, "chance": N, "bet": None}

async def handle_dig(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет шахты! Нужна комната 12.",
            parse_mode=ParseMode.HTML
        )
        return
    await ensure_mine(uid)
    m = await get_mine(uid)
    if m["pickaxe"] == 0 or m["durability"] <= 0:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет кирки или она сломана!\n"
            f"Купи кирку: <code>Купить кирку [1/2/3]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    pickaxe_idx = m["pickaxe"] - 1
    depth = m["depth"]
    chances = get_mine_chances_by_depth(depth, pickaxe_idx)
    if not chances:
        await update.message.reply_text(
            f"{user_link(uid, username)}, на этой глубине ничего не найти. Копай глубже!",
            parse_mode=ParseMode.HTML
        )
        return
    # Выбираем случайный ресурс с учётом шансов
    keys = list(chances.keys())
    weights = [chances[k] for k in keys]
    chosen_key = random.choices(keys, weights=weights, k=1)[0]
    chosen_res = MINE_RESOURCES[chosen_key]
    chance_val = chances[chosen_key]

    DIG_PENDING[uid] = {"resource": chosen_key, "chance": chance_val}

    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты нашёл {chosen_res['emoji']} {chosen_res['name']}.\n"
        f"Ты можешь его выкопать с вероятностью {chance_val}%\n"
        f"📉 Глубина: {depth} м."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ Копать", callback_data=f"dig_do_{uid}"),
         InlineKeyboardButton("🚬 Пропустить", callback_data=f"dig_skip_{uid}")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_buy_pickaxe(update: Update, user: dict, pickaxe_num: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"{user_link(uid, username)}, для покупки кирки нужна комната 12 (Шахта)!",
            parse_mode=ParseMode.HTML
        )
        return
    if pickaxe_num not in PICKAXES:
        await update.message.reply_text(f"{user_link(uid, username)}, номер кирки от 1 до 3!", parse_mode=ParseMode.HTML)
        return
    pk = PICKAXES[pickaxe_num]
    if user["balance"] < pk["price"]:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    await ensure_mine(uid)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (pk["price"], uid))
        await db.execute("UPDATE mine SET pickaxe = ?, durability = ? WHERE user_id=?",
                         (pickaxe_num, pk["durability"], uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты купил(-а) {pk['emoji']} {pk['name']} за {fmt_smart(pk['price'])} кр.!",
        parse_mode=ParseMode.HTML
    )

async def handle_sell_mine_resource(update: Update, user: dict, res_key: str, qty_str: str) -> bool:
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_mine(uid)
    m = await get_mine(uid)
    if res_key not in MINE_RESOURCES:
        return False
    res = MINE_RESOURCES[res_key]
    available = m.get(res["col"], 0)
    if available <= 0:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет {res['name'].lower()}!",
            parse_mode=ParseMode.HTML
        )
        return True
    if qty_str.lower() in ("всё", "все"):
        qty = available
    else:
        try:
            qty = int(qty_str)
        except:
            qty = available
    qty = min(qty, available)
    earnings = qty * res["sell"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE mine SET {res['col']} = {res['col']} - ? WHERE user_id=?", (qty, uid))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (earnings, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты продал(-а) {qty} кг. {res['emoji']} {res['name']} за {fmt_smart(earnings)} кр.!",
        parse_mode=ParseMode.HTML
    )
    return True


# ── Казино (игры с картами — Очко) ───────────────────────────────────────────
