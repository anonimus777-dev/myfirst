"""Общая игровая экономика и безопасные операции с игровой валютой."""
# -*- coding: utf-8 -*-
import aiosqlite
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import DB_PATH, OCHKO_GAMES, HO_GAMES, CARD_DECK
from вспомогательные.вспомогательные_функции import (
    fmt_smart, user_link, card_value, hand_value, hand_str, get_vip_barrel_limit,
    get_current_income,
)
from вспомогательные.проверки import require_bunker
from база_данных.база import get_user, get_total_income


async def get_barrels(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM barrels WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return {"user_id": user_id, "barrel_1": 0, "barrel_2": 0, "barrel_3": 0}

async def ensure_barrels(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO barrels (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def handle_barrels_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_barrels(uid)
    b = await get_barrels(uid)
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот твои бочки:\n"
        f"🛢 1. Обычная бочка: {b['barrel_1']} шт.\n"
        f"🏺 2. Бронзовая бочка: {b['barrel_2']} шт.\n"
        f"⚱️ 3. Золотая бочка: {b['barrel_3']} шт.\n\n"
        f"🧾 Цены на бочки:\n"
        f"   🛢 Обычная бочка — 5,000 кр.\n"
        f"   🏺 Бронзовая бочка — 30,000 кр.\n"
        f"   ⚱️ Золотая бочка — 30 BB-coins\n\n"
        f"ℹ️ Бочку можно купить командой — <code>Купить бочку</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_buy_barrel(update: Update, user: dict, parts: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_barrels(uid)
    # parts — это raw.split(), индексы: 0="купить", 1="бочку", 2=номер, 3=кол-во
    if len(parts) < 4:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно купить бочки!\n"
            f"Курс бочек — <code>Бочки</code>\n\n"
            f"Пример: <code>Купить бочку [номер] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        num = int(parts[2])
        qty = int(parts[3])
    except:
        await update.message.reply_text("Неверный формат. Пример: Купить бочку 1 5", parse_mode=ParseMode.HTML)
        return
    if num not in (1, 2, 3):
        await update.message.reply_text(f"{user_link(uid, username)}, номер бочки от 1 до 3!", parse_mode=ParseMode.HTML)
        return
    if qty <= 0:
        return
    prices = {1: 5000, 2: 30000}
    if num in prices:
        cost = prices[num] * qty
        if user["balance"] < cost:
            await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        col = f"barrel_{num}"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE users SET balance = balance - ? WHERE user_id=?", (cost, uid))
            await db.execute(f"UPDATE barrels SET {col} = {col} + ? WHERE user_id=?", (qty, uid))
            await db.commit()
        await update.message.reply_text(
            f"{user_link(uid, username)}, ты купил(-а) {qty} шт. бочки #{num} за {fmt_smart(cost)} кр.!",
            parse_mode=ParseMode.HTML
        )
    else:
        # Золотая бочка — за BB-coins
        cost_bb = 30 * qty
        if user["bb_coins"] < cost_bb:
            await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно BB-coins!", parse_mode=ParseMode.HTML)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bb_coins = bb_coins - ? WHERE user_id=?", (cost_bb, uid))
            await db.execute("UPDATE barrels SET barrel_3 = barrel_3 + ? WHERE user_id=?", (qty, uid))
            await db.commit()
        await update.message.reply_text(
            f"{user_link(uid, username)}, ты купил(-а) {qty} шт. золотой бочки за {cost_bb} BB-coins!",
            parse_mode=ParseMode.HTML
        )

async def handle_open_barrel(update: Update, user: dict, parts: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_barrels(uid)
    # parts индексы: 0="открыть", 1="бочку", 2=номер, 3=кол-во
    if len(parts) < 3:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно открыть бочку!\n\n"
            f"Пример: <code>Открыть бочку [номер] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        num = int(parts[2])
        qty = int(parts[3]) if len(parts) >= 4 else 1
    except:
        await update.message.reply_text("Неверный формат. Пример: Открыть бочку 1 5", parse_mode=ParseMode.HTML)
        return

    if num not in (1, 2, 3):
        await update.message.reply_text(f"{user_link(uid, username)}, номер бочки от 1 до 3!", parse_mode=ParseMode.HTML)
        return

    max_open = get_vip_barrel_limit(vip)
    qty = min(qty, max_open)

    b = await get_barrels(uid)
    col = f"barrel_{num}"
    available = b[col]
    if available <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя нет бочки #{num}!", parse_mode=ParseMode.HTML)
        return
    qty = min(qty, available)

    total_income = await get_total_income(uid)

    # Считаем награды
    total_coins = 0
    total_rating = 0
    total_stim = 0
    total_weapon = 0

    barrel_names = {1: ("🛢 Обычную бочку", 1000, 4500), 2: ("🏺 Бронзовую бочку", 5000, 30000), 3: ("⚱️ Золотую бочку", 0, 0)}
    bname = barrel_names[num][0]

    for _ in range(qty):
        if num == 1:
            total_coins += random.randint(1000, 4500)
            if random.random() < 0.20:
                total_rating += random.randint(1, 2)
            if random.random() < 0.10:
                total_stim += 1
            if random.random() < 0.10:
                total_weapon += 1
        elif num == 2:
            total_coins += random.randint(5000, 30000)
            if random.random() < 0.25:
                total_rating += random.randint(1, 2)
            if random.random() < 0.10:
                total_stim += random.randint(1, 2)
            if random.random() < 0.10:
                total_weapon += random.randint(1, 2)
        else:
            # Золотая — 300% от дохода в час
            total_coins += int(total_income * 3.0)
            total_rating += random.randint(5, 50)
            total_stim += random.randint(5, 20)
            total_weapon += random.randint(5, 20)

    # Обновляем БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE barrels SET {col} = {col} - ? WHERE user_id=?", (qty, uid))
        await db.execute("UPDATE users SET balance = balance + ?, rating = rating + ? WHERE user_id=?",
                         (total_coins, total_rating, uid))
        await db.commit()

    drops = [f"💰 {fmt_smart(total_coins)} крышек"]
    if total_rating > 0:
        drops.append(f"🏆 {total_rating} рейтинг")
    if total_stim > 0:
        drops.append(f"💉 {total_stim} стимулятора(-ов)")
    if total_weapon > 0:
        drops.append(f"🔫 {total_weapon} оружие(-я)")

    drops_text = "\n".join(drops)
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты открыл {bname} ({qty}шт.)\n"
        f"📦 Тебе выпало:\n"
        f"<blockquote>{drops_text}</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Починить бункер ───────────────────────────────────────────────────────────

async def handle_ochko_start(update: Update, user: dict, bet: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if user["balance"] < bet:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    if bet <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, ставка должна быть больше 0!", parse_mode=ParseMode.HTML)
        return

    deck = CARD_DECK.copy()
    random.shuffle(deck)

    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Сохраняем состояние игры в user_data
    context_key = f"ochko_{uid}"
    game_state = {
        "bet": bet,
        "deck": deck,
        "player": player_hand,
        "dealer": dealer_hand,
        "username": username,
    }

    # Списываем ставку
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, uid))
        await db.commit()

    pval = hand_value(player_hand)
    dval = hand_value(dealer_hand)

    text = (
        f"♣️ {user_link(uid, username)}, ты запустил игру 21\n"
        f"· · · · · · · · · · · · · · ·\n"
        f"💰 Ставка: {fmt_smart(bet)} кр.\n\n"
        f"🎩 Дилер:\n"
        f"{hand_str(dealer_hand[:1])} • ? | {card_value(dealer_hand[0])}\n"
        f"──────────────────\n"
        f"👊 Ты:\n"
        f"{hand_str(player_hand)} | {pval}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 СТОП", callback_data=f"ochko_stop_{uid}"),
         InlineKeyboardButton("🃏 ЕЩЁ", callback_data=f"ochko_hit_{uid}")]
    ])
    msg = await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    OCHKO_GAMES[uid] = {**game_state, "msg_id": msg.message_id, "chat_id": update.message.chat_id}

async def handle_ho_start(update: Update, user: dict, bet: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if user["balance"] < bet:
        await update.message.reply_text(f"{user_link(uid, username)}, недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    if bet <= 0:
        await update.message.reply_text("Ставка должна быть больше 0!", parse_mode=ParseMode.HTML)
        return
    game_id = str(uid)
    HO_GAMES[game_id] = {
        "p1": uid, "p2": None,
        "p1_name": username, "p2_name": "?",
        "bet": bet, "board": [0]*9, "turn": 1,
        "chat_id": update.message.chat_id,
        "active": False,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, uid))
        await db.commit()
    text = (
        f"❌⭕️ Крестики-нолики на {fmt_smart(bet)} GPoint\n\n"
        f"❌ {user_link(uid, username)}\n"
        f"⭕️ ?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Играть", callback_data=f"ho_join_{game_id}"),
         InlineKeyboardButton("🛑 Отменить", callback_data=f"ho_cancel_{game_id}")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

def ho_check_winner(board: list) -> int:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] != 0:
            return board[a]
    if all(x != 0 for x in board):
        return -1  # ничья
    return 0  # игра продолжается

def ho_keyboard(game_id: str, board: list) -> InlineKeyboardMarkup:
    symbols = {0: "⬜", 1: "❌", 2: "⭕️"}
    rows = []
    for i in range(3):
        row = []
        for j in range(3):
            idx = i*3+j
            row.append(InlineKeyboardButton(
                symbols[board[idx]],
                callback_data=f"ho_move_{game_id}_{idx}" if board[idx] == 0 else f"ho_no_{idx}"
            ))
        rows.append(row)
    return InlineKeyboardMarkup(rows)

async def handle_fuel(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    total_income = await get_total_income(uid)
    fuel_per_hour = max(1, total_income // 5)
    max_fuel = fuel_per_hour * 12  # на 12 часов
    current_fuel = user.get("fuel", 0)

    text = (
        f"🙎‍♂️ {user_link(uid, username)}\n"
        f"🛢 Нефтехранилище\n\n"
        f"⛽️ Твой текущий запас бензина: {fmt_smart(int(current_fuel))}/{fmt_smart(max_fuel)} л.\n"
        f"🪫 Расход: {fmt_smart(fuel_per_hour)} л./час\n"
        f"💵 Цена за литр: 1 крышка"
    )
    need_full = max(0, max_fuel - current_fuel)
    need_hour = max(0, fuel_per_hour - current_fuel)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🛢 Купить до полного бака ({fmt_smart(int(need_full))} кр.)",
                              callback_data=f"fuel_full_{uid}")],
        [InlineKeyboardButton(f"⛽️ Купить на 1 час ({fmt_smart(fuel_per_hour)} кр.)",
                              callback_data=f"fuel_hour_{uid}")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def fuel_consume_job(context: ContextTypes.DEFAULT_TYPE):
    """Расходует бензин каждые 30 минут."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT room_num, level FROM rooms WHERE user_id=?", (uid,)) as cur2:
                rooms = await cur2.fetchall()
            if not rooms:
                continue
            total_income = sum(get_current_income(r[0], r[1]) for r in rooms)
            fuel_per_half = max(1, total_income // 5) // 2
            await db.execute(
                "UPDATE users SET fuel = MAX(fuel - ?, 0) WHERE user_id=?",
                (fuel_per_half, uid)
            )
        await db.commit()

async def cmd_cases_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_barrels_info(update, user)
