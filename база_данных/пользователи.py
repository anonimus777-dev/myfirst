# -*- coding: utf-8 -*-
import aiosqlite
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import DB_PATH, ADMIN_IDS, PROMO_CODES, RATING_BUY_PRICE, RATING_SELL_PRICE, MOSCOW_TZ
from вспомогательные.вспомогательные_функции import (
    fmt_smart, fmt_bottles, user_link, safe_nick, parse_bet, get_vip_transfer_limit,
    get_vip_level_name, get_balance_limit,
)
from вспомогательные.проверки import require_bunker
from база_данных.база import get_user, get_total_income, get_rooms
from клавиатуры.общие import donate_keyboard, back_keyboard


async def handle_balance(update: Update, user: dict):
    rooms = await get_rooms(user["user_id"])
    balance_limit = get_balance_limit(rooms)
    username = user["username"] or "Игрок"
    bal_fmt = fmt_smart(user['balance'])
    lim_fmt = fmt_smart(balance_limit)
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"💰 Баланс: {bal_fmt}/{lim_fmt} кр.\n"
        f"🍾 Бутылки: {int(user['bottles'])}\n"
        f"🪙 BB-coins: {fmt_smart(user['bb_coins'])}\n"
        f"🏆 Рейтинг: {fmt_smart(user.get('rating', 0))}"
    )
    await update.message.reply_text(text, reply_to_message_id=update.message.message_id, parse_mode=ParseMode.HTML)


# ── Donate ───────────────────────────────────────────────────────────────────

async def handle_change_nick(update: Update, user: dict, new_nick: str):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    max_len = {0: 20, 1: 25, 2: 30, 3: 40, 4: 50}.get(vip, 20)
    if len(new_nick) > max_len:
        await update.message.reply_text(
            f"{user_link(uid, username)}, ник слишком длинный! Максимум {max_len} символов."
        , parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_nick, uid))
        await db.commit()
    await update.message.reply_text(f"{user_link(uid, username)}, ты успешно изменил(-а) имя на {new_nick}!", parse_mode=ParseMode.HTML)


# ── Balance / bb command ─────────────────────────────────────────────────────

async def handle_rating(update: Update, user: dict):
    username = user["username"] or "Игрок"
    rating = user.get("rating", 0)
    await update.message.reply_text(f"{user_link(user['user_id'], username)}, твой рейтинг {fmt_smart(rating)} 🏆", parse_mode=ParseMode.HTML)

async def handle_buy_rating(update: Update, user: dict, amount: int):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    cost = amount * RATING_BUY_PRICE
    if user["balance"] < cost:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя не достаточно денег!", parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ?, rating = rating + ? WHERE user_id = ?",
                         (cost, amount, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно купил(-а) {fmt_smart(amount)} рейтинг за {fmt_smart(cost)} крышек!"
    , parse_mode=ParseMode.HTML)

async def handle_sell_rating(update: Update, user: dict, amount: int):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    if user.get("rating", 0) < amount:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя не достаточно рейтинга!", parse_mode=ParseMode.HTML)
        return
    earn = amount * RATING_SELL_PRICE
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ?, rating = rating - ? WHERE user_id = ?",
                         (earn, amount, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно продал(-а) {fmt_smart(amount)} рейтинг за {fmt_smart(earn)} крышек!"
    , parse_mode=ParseMode.HTML)


# ── Nickname change ──────────────────────────────────────────────────────────

async def handle_ref(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    # Count invited (simplified — not tracking in DB currently, show 0)
    invited = 0
    ref_link = f"https://t.me/darkhostrobot?start={uid}"
    share_link = f"https://t.me/share/url?url={ref_link}"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты пригласил(-а) {invited} 👨‍👧‍👦\n"
        f"🤭 Когда приглашенный человек купит 10 комнату, вы вдвоём получите по 20 BB-Coins 🪙"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Поделиться ссылкой ↩️", url=share_link)],
        [InlineKeyboardButton("Добавить бота в группу 🤖", url="https://t.me/darkhostrobot?startgroup")],
    ])
    await update.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode=ParseMode.HTML)


# ── Limits ───────────────────────────────────────────────────────────────────

async def handle_bonus(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    total_income = await get_total_income(uid)

    now_moscow = datetime.now(MOSCOW_TZ)
    today_str = now_moscow.strftime("%Y-%m-%d")

    # VIP4: can claim twice (every 12h), others once per day (reset 00:00 MSK)
    last_bonus = user.get("last_bonus")

# Следующее окно: 00:00 или 12:00 МСК
    now_hour = now_moscow.hour
    today_date = now_moscow.date()

    if vip >= 4:
        # Два окна: 00:00 и 12:00
        if now_hour < 12:
            current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=0)))
            next_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=12)))
        else:
            current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=12)))
            next_window = MOSCOW_TZ.localize(datetime.combine(today_date + timedelta(days=1), datetime.min.time().replace(hour=0)))

        if last_bonus:
            last_dt = datetime.fromisoformat(last_bonus)
            if last_dt.tzinfo is None:
                last_dt = MOSCOW_TZ.localize(last_dt)
            if last_dt >= current_window:
                diff = next_window - now_moscow
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                await update.message.reply_text(f"⏳ Уже забирал! Следующий через: {h} ч. {m} мин.")
                return
    else:
        # Одно окно: 00:00
        current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time()))
        next_window = MOSCOW_TZ.localize(datetime.combine(today_date + timedelta(days=1), datetime.min.time()))

        if last_bonus:
            last_dt = datetime.fromisoformat(last_bonus)
            if last_dt.tzinfo is None:
                last_dt = MOSCOW_TZ.localize(last_dt)
            if last_dt >= current_window:
                diff = next_window - now_moscow
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                await update.message.reply_text(f"⏳ Уже забирал! Следующий через: {h} ч. {m} мин.")
                return

    # Calculate bonus: 180-240% of total income
    multiplier = random.uniform(1.8, 2.4)
    bonus = int(total_income * multiplier)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
            (bonus, now_moscow.isoformat(), uid)
        )
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, твой ежедневный бонус: {fmt_smart(bonus)} кр."
    , parse_mode=ParseMode.HTML)


# ── Top handler (message) ─────────────────────────────────────────────────────

async def handle_promo(update: Update, user: dict, promo: str):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    promo_lower = promo.lower()

    if promo_lower not in PROMO_CODES:
        await update.message.reply_text(f"{user_link(uid, username)}, такого промокода не существует!", parse_mode=ParseMode.HTML)
        return

    # Check if used
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM used_promos WHERE user_id=? AND promo=?", (uid, promo_lower)) as cur:
            if await cur.fetchone():
                await update.message.reply_text(f"{user_link(uid, username)}, этот промокод уже недействителен!", parse_mode=ParseMode.HTML)
                return

    promo_data = PROMO_CODES[promo_lower]
    reward_type = promo_data["reward_type"]
    amount = promo_data["amount"]

    async with aiosqlite.connect(DB_PATH) as db:
        if reward_type == "coins":
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
            reward_text = f"💰 {fmt_smart(amount)} крышек"
        elif reward_type == "bottles":
            await db.execute("UPDATE users SET bottles = bottles + ? WHERE user_id=?", (amount, uid))
            reward_text = f"🍾 {fmt_smart(amount)} шт."
        elif reward_type == "rating":
            await db.execute("UPDATE users SET rating = rating + ? WHERE user_id=?", (amount, uid))
            reward_text = f"🏆 {fmt_smart(amount)} рейтинга"
        elif reward_type == "bbcoins":
            await db.execute("UPDATE users SET bb_coins = bb_coins + ? WHERE user_id=?", (amount, uid))
            reward_text = f"🪙 {fmt_smart(amount)} BB-coins"
        elif reward_type == "exp":
            reward_text = f"⭐️ {fmt_smart(amount)} опыта"
        else:
            reward_text = f"{fmt_smart(amount)} бонусов"

        await db.execute("INSERT OR IGNORE INTO used_promos (user_id, promo) VALUES (?, ?)", (uid, promo_lower))
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, тебе начислено:\n{reward_text}\n\n🧡 Приятной игры! 🧡"
    , parse_mode=ParseMode.HTML)


# ── Referral ─────────────────────────────────────────────────────────────────

async def handle_donate(update: Update, user: dict):
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"Команды:\n"
        f"   ⚖️ <code>Донат курс</code>\n"
        f"   🪙 Донат купить крышки [кол. тысяч]\n"
        f"   💹 Донат купить рейтинг [кол. рейтинга]\n"
        f"   👨‍👨‍👦‍👦 Донат купить людей [кол. людей]\n"
        f"   🎫 Донат купить вип [уровень]\n"
        f"   🚘 Донат купить авто [4/5/6]\n\n"
        f"Доп. контакты для доната - Alkyrin\n\n"
        f"<blockquote>🔥 На сайте действует скидка на донат 50% 🔥</blockquote>"
    )
    await update.message.reply_text(text, reply_markup=donate_keyboard(), parse_mode=ParseMode.HTML)

async def handle_donate_rate(update: Update, user: dict):
    username = user["username"] or "Игрок"
    # 1% of total income
    total_income = await get_total_income(user["user_id"])
    coin_rate = max(1, int(total_income * 0.05))
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"Курс обмена BB-coins:\n"
        f"   🪙 1 BB-coins -> {fmt_smart(coin_rate)} крышек\n"
        f"   💹 10 BB-coins -> 1 рейтинг\n"
        f"   👨‍👨‍👦‍👦 5 BB-coins -> 1 человек\n"
        f"   ⚡️ 200 BB-coins -> VIP1\n"
        f"   🔥 600 BB-coins -> VIP2\n"
        f"   💎 1200 BB-coins -> VIP3\n"
        f"   ⭐️ 2000 BB-coins -> VIP4\n"
        f"   🚘 250/350/450 BB-coins -> Авто 4/5/6\n\n"
        f"Курс покупки BB-coins:\n"
        f"  1 ⭐️ -> 1 BB-coins\n"
        f"<blockquote>🔥 Действует скидка на донат 50% 🔥\n\n"
        f"При покупке VIP4 если у вас есть VIP3, цена будет составлять 800 BB-coins 🔥</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Statuses ─────────────────────────────────────────────────────────────────

async def handle_statuses(update: Update, user: dict):
    username = user["username"] or "Игрок"
    text = (
        f"👑 Информация о статусах 👑\n\n"
        f"⚡️ VIP1 ⚡️ (200 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Увеличенный шанс в азартных играх\n"
        f" - Улучшения комнаты на 20 уровней\n"
        f" - 150 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 5.000\n"
        f" - Лимит на открытие бочек 5🛢\n"
        f" - Длина ника до 25 символов\n"
        f" - Буст дохода +1%\n"
        f" - Выращивание в теплице до 5 растений за раз 🌱"
        f"</blockquote>\n"
        f"🔥 VIP2 🔥 (600 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 14/11/8/5/4 минуты\n"
        f" - Улучшения комнаты на 100 уровней\n"
        f" - 150 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 8.000\n"
        f" - Лимит воды увеличен до 50💧\n"
        f" - Лимит на открытие бочек 10🛢\n"
        f" - Длина ника до 30 символов\n"
        f" - Буст дохода +2%\n"
        f" - Выращивание в теплице до 10 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 45 сек"
        f"</blockquote>\n"
        f"💎 VIP3 💎 (1200 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Ещё более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 13/10/7/4/3 минуты\n"
        f" - Улучшения комнаты на 1'000 уровней\n"
        f" - 200 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 15.000\n"
        f" - Лимит воды увеличен до 75💧\n"
        f" - Лимит на открытие бочек 25🛢\n"
        f" - Длина ника до 40 символов\n"
        f" - Просмотр ID юзеров\n"
        f" - Просмотр профилей других игроков\n"
        f" - Буст дохода +3%\n"
        f" - Выращивание в теплице до 15 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 30 сек\n"
        f"   ○ 100 ур. = 1 мин"
        f"</blockquote>\n"
        f"⭐️ VIP4 ⭐️ (2000 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - 2 ежедневных бонуса в сутки\n"
        f" - Ещё более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 12/9/6/3/2 минуты\n"
        f" - Улучшения комнаты на 5'000 уровней\n"
        f" - 250 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 25.000\n"
        f" - Лимит воды увеличен до 100💧\n"
        f" - Лимит на открытие бочек 50🛢\n"
        f" - Длина ника до 50 символов\n"
        f" - Просмотр ID юзеров\n"
        f" - Просмотр профилей других игроков\n"
        f" - Возможность скрыть свой бункер\n"
        f" - Буст дохода +4%\n"
        f" - Выращивание в теплице до 20 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 20 сек\n"
        f"   ○ 100 ур. = 45 сек\n"
        f"   ○ 1000 ур. = 2 мин"
        f"</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Promo codes ──────────────────────────────────────────────────────────────

async def handle_limits(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    transfer_limit = get_vip_transfer_limit(vip)
    await update.message.reply_text(
        f"🙎‍♂️ {user_link(uid, username)}, твои лимиты:\n"
        f"Передачи денег - {fmt_smart(transfer_limit)}/{fmt_smart(transfer_limit)}"
    , parse_mode=ParseMode.HTML)


# ── RP commands ───────────────────────────────────────────────────────────────

async def cmd_balance_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_balance(update, user)

async def cmd_ref_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_ref(update, user)

async def cmd_bonus_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_bonus(update, user)

async def cmd_donation_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_donate(update, user)

async def cmd_rating_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_rating(update, user)
