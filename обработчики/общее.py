"""Обработчики общих команд. Перенесено из исходного монолита; зависимости будут вынесены в следующие коммиты."""

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle referral
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
        except:
            pass

    await update.message.reply_text(
        "Добро пожаловать в игру 'Бункер'! Чтобы разобраться как играть, напишите Помощь\n\n"
        "Так же у нас есть чат, где вы сможете весело провести время с остальными https://t.me/bfgbunker_chat",
        disable_web_page_preview=True
    , parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] if user else (update.effective_user.first_name or "Игрок")
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, выберите категорию:\n"
        "   📚 Основное\n"
        "   🎮 Игры\n"
        "   🏄‍♀️ Активности\n"
        "   💬 Чаты\n\n"
        "💬 Так же у нас есть общая беседа №1\n"
        "🆘 По всем вопросам - @Alkyrin"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=help_main_keyboard(), parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=help_main_keyboard(), parse_mode=ParseMode.HTML)


async def cmd_bunker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    text = await build_bunker_text(uid)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


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

    if broke:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bunker_broken = 1 WHERE user_id=?", (user_id,))
            await db.commit()
        # Возвращаем два значения: сообщение об улучшении и флаг пожара
        return f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня за {fmt_smart(total_cost)} кр.", True

    return (
        f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня\n"
        f"за {fmt_smart(total_cost)} кр."
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

def donate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Купить 🪙 BBCoins", url="https://t.me/Alkyrin")],
        [InlineKeyboardButton("💰 Сайт для доната 💰", url="https://t.me/Alkyrin")],
    ])


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

async def handle_rp_list(update: Update, user: dict):
    username = user["username"] or "Игрок"
    commands_list = list(RP_COMMANDS.keys())
    lines = [f"🙎‍♂️ {user_link(user['user_id'], username)}, все доступные РП команды:"]
    for i, cmd in enumerate(commands_list, 1):
        lines.append(f"{i}) {cmd.capitalize()}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_rp_action(update: Update, user: dict, action: str):
    username = user["username"] or "Игрок"
    past_form = RP_COMMANDS[action][0]
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(f"{user_link(user['user_id'], username)}, ты должен ответить на сообщение!", parse_mode=ParseMode.HTML)
        return
    target_uid = reply.from_user.id
    target_user = await get_user(target_uid)
    target_name = (target_user["username"] if target_user and target_user["username"] else reply.from_user.first_name) or "Игрок"
    uid_sender = user["user_id"]
    await update.message.reply_text(
        f'🙎‍♂️ {user_link(uid_sender, username)} {past_form} {user_link(target_uid, target_name)}',
        parse_mode=ParseMode.HTML
    )


# ── Daily bonus ───────────────────────────────────────────────────────────────

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

async def handle_top(update: Update, user: dict, category: str = "rating"):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = await build_top_text(uid, category)
    kb = top_keyboard(category)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Main message handler ──────────────────────────────────────────────────────


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


async def cmd_rooms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_rooms_list(update, context)

async def cmd_top_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_top(update, user, "rating")

async def cmd_cases_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_barrels_info(update, user)

async def cmd_rating_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_rating(update, user)

