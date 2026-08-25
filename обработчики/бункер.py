"""Обработчики бункера, комнат, бочек, ремонта и топлива.

Перенесено из исходного монолита.
"""

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


async def build_bunker_text(user_id: int) -> str:
    user = await get_user(user_id)
    rooms = await get_rooms(user_id)
    username = user["username"] or "Игрок"
    balance_limit = get_balance_limit(rooms)
    total_income = await get_total_income(user_id)
    vip = user.get("vip", 0)

    rooms_text = ""
    for r in rooms:
        rn = r["room_num"]
        emoji = NUM_EMOJIS.get(rn, f"{rn}.")
        rooms_text += f"  {emoji} {ROOMS_DATA[rn]['name']} {r['level']} ур.\n"

    owned_nums = {r["room_num"] for r in rooms}
    for rn in range(5, 20):
        if rn not in owned_nums:
            req = ROOMS_DATA[rn]["unlock_people"]
            price_r = ROOM_BUY_PRICES[rn]
            emoji = NUM_EMOJIS.get(rn, f"{rn}.")
            if user["people"] >= req:
                rooms_text += f"  {emoji} Можно купить! '{ROOMS_DATA[rn]['name']}'\n"
                rooms_text += f"          Цена: {fmt_smart(price_r)} крышек\n"
            break

    vip_badges = {1: "⚡️ VIP1 ⚡️", 2: "🔥🔥 VIP2 🔥🔥", 3: "💎💎💎 VIP3 💎💎💎", 4: "⭐️⭐️⭐️ VIP4 ⭐️⭐️⭐️"}
    vip_line = (vip_badges[vip] + "\n") if vip > 0 else ""
    custom_status = user.get("custom_status")
    custom_line = (custom_status + "\n") if custom_status else ""

    bal_fmt = fmt_smart(user['balance'])
    lim_fmt = fmt_smart(balance_limit)
    rating_fmt = fmt_smart(user.get('rating', 0))

    has_fuel = user.get("fuel", 0) > 0
    if not has_fuel:
        income_line = "💵 Бункер не работает! Нет бензина❗️"
    elif user.get("bunker_broken", 0):
        income_line = (
            f"🔴 В бункере пожар!\n"
            f"Прибыль уменьшена на 50%! 🔴\n"
            f"💵 Общая прибыль {fmt_smart(total_income // 2)} кр./час"
        )
    else:
        income_line = f"💵 Общая прибыль {fmt_smart(total_income)} кр./час"

    return (
        f"{custom_line}{vip_line}"
        f"🙎‍♂️ {user_link(user_id, username)}\n"
        f"🏢 Бункер №{user_id}\n\n"
        f"💰 Баланс: {bal_fmt}/{lim_fmt} кр.\n"
        f"🍾 Бутылок: {int(user['bottles'])}\n"
        f"🪙 BB-coins: {fmt_smart(user['bb_coins'])}\n"
        f"🏆 Рейтинг: {rating_fmt}\n"
        f"🧍 Людей в бункере: {user['people']}\n"
        f"     ↳ Людей в очереди в бункер: {user['queue']}/5\n\n"
        f"🏠 Комнаты:\n<blockquote expandable>{rooms_text}</blockquote>"
        f"  Макс. вместимость людей: {user['people']}\n\n"
        f"{income_line}\n"
        f"📅 Дата регистрации: {user['registered_at']}"
    )


async def build_room_text(user_id: int, room_num: int, use_bottles: bool = False) -> str:
    user = await get_user(user_id)
    username = user["username"] or "Игрок"
    level = await get_room_level(user_id, room_num)
    if level == 0:
        return None
    rdata = ROOMS_DATA[room_num]
    income = get_current_income(room_num, level)
    next_cost = get_upgrade_cost(room_num, level)

    extra_text = ""
    if room_num == 7:
        ex = await get_room_extra(user_id, 7)
        stock = ex["med_stock"] if ex else 0
        extra_text = f"\n⚔️ Мед.склад: {stock} ед.\n    Цена: 3.000 кр./шт\n"
    elif room_num == 9:
        ex = await get_room_extra(user_id, 9)
        stock = ex["weapon_stock"] if ex else 0
        extra_text = f"\n⚔️ Склад оружия: {stock} ед.\n    Цена: 6.000 кр./шт\n"
    elif room_num == 18:
        ex = await get_room_extra(user_id, 18)
        diamond = ex["diamond"] if ex else 0
        uranium = ex["uranium"] if ex else 0
        extra_text = (
            f"\n⚛️ Создание материи:\n"
            f"    💎 Алмаз - {diamond}/1\n"
            f"    ☢️ Уран - {uranium}/5\n"
            f"    ⏳ Время - 20 минут\n"
        )
    elif room_num == 19:
        ex = await get_room_extra(user_id, 19)
        matter = ex["matter"] if ex else 0
        extra_text = (
            f"\n⚛️ Использование материи:\n"
            f"Материю можно использовать как топливо для бункера вместо бензина. "
            f"1 материи хватает на 12 часов питания всего бункера!\n"
            f"🛢️ Текущее количество материи: {matter} 🟣\n"
        )

    cost_line = f"🔝 Следующее улучшение стоит: {fmt_bottles(next_cost / 10000)} 🍾" if use_bottles else f"🔝 Следующее улучшение стоит: {fmt_smart(next_cost)} кр."
    return (
        f"🙎‍♂️ {user_link(user_id, username)}\n"
        f"🏠 Комната №{room_num} {rdata['name']}\n\n"
        f"📊 Уровень: {level}\n"
        f"💵 Прибыль: {fmt_smart(income)} кр/час\n"
        f"🧍 Макс. человек: {rdata['capacity'] + (level - 1) * 2}\n"
        f"{extra_text}\n"
        f"{cost_line}"
    )


async def build_top_text(user_id: int, category: str) -> str:
    user = await get_user(user_id)
    username = user["username"] or "Игрок"

    cat_config = {
        "rating":     ("🏆 Рейтинг", "рейтинга", "rating", "🏆"),
        "income":     ("💵 Доход", "кр/час", None, "💵"),
        "coins":      ("💰 Крышки", "крышек", "balance", "💰"),
        "greenhouse": ("⭐️ Теплица", "опыта", None, "greenhouse_stub", "⭐️"),
        "wasteland":  ("🏜 Пустошь", "", "wasteland_hours", "🏜"),
        "guilds":     ("🏰 Гильдии", "", None, "guilds_stub", "🏰"),
        "residents":  ("🧍 Жители", "человек", "people", "🧍"),
        "bottles":    ("🍾 Бутылки", "бутылок", "bottles", "🍾"),
    }

    cat_data = cat_config.get(category, ("🏆 Рейтинг", "рейтинга", "rating", "🏆"))
    title, unit, field = cat_data[0], cat_data[1], cat_data[2]
    stub = cat_data[3] if len(cat_data) > 4 else None

    # Заглушки для ещё не реализованных топов
    if stub == "guilds_stub":
        text = (
            "🏣 Топ гильдий\n\n"
            "⚔️ ТОП 5 по атаке:\nНет гильдий\n\n"
            "🛡 ТОП 5 по защите:\nНет гильдий"
        )
        return text

    if stub == "greenhouse_stub":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT g.user_id, u.username, g.exp FROM greenhouse g "
                "JOIN users u ON g.user_id = u.user_id ORDER BY g.exp DESC LIMIT 10"
            ) as cur:
                top_rows = await cur.fetchall()
            async with db.execute(
                "SELECT COUNT(*) FROM greenhouse WHERE exp > (SELECT exp FROM greenhouse WHERE user_id=?)",
                (user_id,)
            ) as cur:
                rank_row = await cur.fetchone()
            user_rank = (rank_row[0] + 1) if rank_row and rank_row[0] is not None else "?"
            async with db.execute("SELECT exp FROM greenhouse WHERE user_id=?", (user_id,)) as cur:
                user_exp_row = await cur.fetchone()
            user_exp = user_exp_row[0] if user_exp_row else 0
        medals = {1:"🥇",2:"🥈",3:"🥉"}
        lines = ["🌱 ТОП 10 ПО ОПЫТУ В ТЕПЛИЦЕ\n"]
        for i, row in enumerate(top_rows, 1):
            uid2, uname2, exp2 = row
            medal = medals.get(i, "🏆")
            lines.append(f"{i}. {medal} {uname2 or 'Игрок'} — {fmt_smart(exp2)} опыта")
        lines.append("\n───────────────")
        lines.append(f"{user_rank}. 🎖 {user_link(user_id, username)} — {fmt_smart(user_exp)} опыта")
        return "\n".join(lines)

    async with aiosqlite.connect(DB_PATH) as db:
        if field:
            async with db.execute(
                f"SELECT user_id, username, {field} FROM users ORDER BY {field} DESC LIMIT 10"
            ) as cur:
                top_rows = await cur.fetchall()
            async with db.execute(
                f"SELECT COUNT(*) FROM users WHERE {field} > (SELECT {field} FROM users WHERE user_id=?)",
                (user_id,)
            ) as cur:
                rank_row = await cur.fetchone()
                user_rank = (rank_row[0] + 1) if rank_row else "?"
            user_val_field = user.get(field, 0)
        else:
            async with db.execute("SELECT user_id, username FROM users") as cur:
                all_users = await cur.fetchall()
            incomes = []
            for uid2, uname2 in all_users:
                async with db.execute("SELECT room_num, level FROM rooms WHERE user_id=?", (uid2,)) as cur2:
                    rs = await cur2.fetchall()
                    inc = sum(get_current_income(r[0], r[1]) for r in rs)
                incomes.append((uid2, uname2 or "Игрок", inc))
            incomes.sort(key=lambda x: x[2], reverse=True)
            top_rows = incomes[:10]
            user_rank = next((i+1 for i, r in enumerate(incomes) if r[0] == user_id), "?")
            user_val_field = next((r[2] for r in incomes if r[0] == user_id), 0)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    def fmt_val(val):
        if category == "wasteland":
            h = int(float(val) // 1)
            m = int((float(val) % 1) * 60)
            return f"{h}ч {m}м"
        return fmt_smart(val)

    if category == "wasteland":
        header = f"🏜 ТОП 10 ПО ВРЕМЕНИ В ПУСТОШИ\n"
    else:
        headers = {
            "rating":    "🏆 ТОП 10 ПО РЕЙТИНГУ\n",
            "income":    "💵 ТОП 10 ПО ДОХОДУ\n",
            "coins":     "💰 ТОП 10 ПО КРЫШКАМ\n",
            "residents": "🧍 ТОП 10 ПО ЖИТЕЛЯМ\n",
            "bottles":   "🍾 ТОП 10 ПО БУТЫЛКАМ\n",
        }
        header = headers.get(category, f"{title} ТОП 10\n")

    lines = [header]
    for i, row in enumerate(top_rows, 1):
        uid2, uname2, val = row[0], row[1] or "Игрок", row[2] or 0
        medal = medals.get(i, "🏆")
        lines.append(f"{i}. {medal} {uname2} — {fmt_val(val)} {unit}")

    lines.append("\n───────────────")
    lines.append(f"{user_rank}. 🎖 {user_link(user_id, username)} — {fmt_val(user_val_field)} {unit}")

    return "\n".join(lines)

# ── Пассивный доход каждые 30 минут ──────────────────────────────────────────


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


