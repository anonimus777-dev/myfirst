from pathlib import Path
import re

p = Path('база_данных/пользователи.py')
s = p.read_text(encoding='utf-8')
s = s.replace('import aiosqlite\nimport random', 'import aiosqlite\nimport asyncio\nimport random', 1)
if 'PROMO_LOCK = asyncio.Lock()' not in s:
    marker = 'from база_данных.база import get_user, get_total_income, get_rooms\n'
    s = s.replace(marker, marker + '\nPROMO_LOCK = asyncio.Lock()\n', 1)
pattern = re.compile(r'async def handle_promo\(update: Update, user: dict, promo: str\):.*?\n\n# ── Referral', re.S)
new_func = '''async def handle_promo(update: Update, user: dict, promo: str):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    promo_lower = promo.strip().lower()
    async with PROMO_LOCK:
        if promo_lower not in PROMO_CODES:
            await update.message.reply_text(f"{user_link(uid, username)}, такого промокода не существует или его использования закончились!", parse_mode=ParseMode.HTML)
            return
        promo_data = PROMO_CODES[promo_lower]
        reward_type = str(promo_data.get("reward_type", "")).lower()
        amount = int(promo_data.get("amount", 0))
        uses_left = int(promo_data.get("uses_left", 1))
        if uses_left <= 0:
            await update.message.reply_text("❌ У этого промокода закончились использования.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM used_promos WHERE user_id=? AND promo=?", (uid, promo_lower)) as cur:
                if await cur.fetchone():
                    await update.message.reply_text(f"{user_link(uid, username)}, ты уже использовал(-а) этот промокод!", parse_mode=ParseMode.HTML)
                    return
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
                await db.execute("INSERT OR IGNORE INTO greenhouse (user_id) VALUES (?)", (uid,))
                await db.execute("UPDATE greenhouse SET exp = exp + ? WHERE user_id=?", (amount, uid))
                reward_text = f"⭐️ {fmt_smart(amount)} опыта"
            else:
                await update.message.reply_text("❌ Неизвестный тип награды промокода.")
                return
            await db.execute("INSERT INTO used_promos (user_id, promo) VALUES (?, ?)", (uid, promo_lower))
            await db.commit()
        uses_left -= 1
        if uses_left <= 0:
            PROMO_CODES.pop(promo_lower, None)
        else:
            promo_data["uses_left"] = uses_left
    await update.message.reply_text(f"{user_link(uid, username)}, тебе начислено:\n{reward_text}\n\n🧡 Приятной игры! 🧡", parse_mode=ParseMode.HTML)


# ── Referral'''
s, n = pattern.subn(new_func, s, count=1)
if n != 1:
    raise SystemExit('handle_promo replacement failed')
p.write_text(s, encoding='utf-8')

p = Path('бот.py')
s = p.read_text(encoding='utf-8')
old = '''        if parts[0].lower() == "добпромо" and len(parts) >= 4:
            promo_code_new = parts[1].lower()
            reward_t = parts[2].lower()
            try:
                reward_a = int(parts[3])
            except:
                await update.message.reply_text("Укажите число для суммы.")
                return
            PROMO_CODES[promo_code_new] = {"reward_type": reward_t, "amount": reward_a}
            await update.message.reply_text(f"✅ Промокод '{promo_code_new}' добавлен: {reward_t} x{reward_a}.", parse_mode=ParseMode.HTML)
            return
'''
new = '''        if parts[0].lower() == "добпромо":
            if len(parts) == 1:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Крышки", callback_data="admin_promo_type_coins"), InlineKeyboardButton("🍾 Бутылки", callback_data="admin_promo_type_bottles")],
                    [InlineKeyboardButton("⭐️ Опыт", callback_data="admin_promo_type_exp"), InlineKeyboardButton("🏆 Рейтинг", callback_data="admin_promo_type_rating")],
                    [InlineKeyboardButton("🪙 BB-coins", callback_data="admin_promo_type_bbcoins")],
                ])
                await update.message.reply_text("Какую выберете?", reply_markup=kb)
                return
            if len(parts) < 4:
                await update.message.reply_text("Формат: <code>ДобПромо код тип сумма [использований]</code>\\nЕсли количество использований не указать, промокод можно использовать 1 раз.", parse_mode=ParseMode.HTML)
                return
            promo_code_new = parts[1].lower()
            reward_t = parts[2].lower()
            if reward_t not in {"coins", "bottles", "rating", "bbcoins", "exp"}:
                await update.message.reply_text("❌ Неизвестный тип награды.")
                return
            try:
                reward_a = int(parts[3])
                uses = int(parts[4]) if len(parts) >= 5 else 1
            except ValueError:
                await update.message.reply_text("Сумма и количество использований должны быть числами.")
                return
            if reward_a <= 0 or uses <= 0:
                await update.message.reply_text("Сумма и количество использований должны быть больше нуля.")
                return
            PROMO_CODES[promo_code_new] = {"reward_type": reward_t, "amount": reward_a, "uses_left": uses}
            await update.message.reply_text(f"✅ Промокод '{promo_code_new}' добавлен: {reward_t} ×{reward_a}.\\n👥 Использований: {uses} (один пользователь — только 1 раз).", parse_mode=ParseMode.HTML)
            return
'''
if old not in s:
    raise SystemExit('admin promo block not found')
s = s.replace(old, new, 1)
marker = '''    elif data.startswith("gh_select_"):\n'''
callback = '''    elif data.startswith("gh_grow_"):
        parts = data.split("_")
        try:
            uid2 = int(parts[2])
            qty = int(parts[3]) if len(parts) > 3 else 1
        except (ValueError, IndexError):
            await query.answer("Некорректная кнопка.", show_alert=True)
            return
        if uid2 != uid:
            await query.answer("Это не твоя теплица!", show_alert=True)
            return
        user2 = await get_user(uid)
        if not user2:
            await query.answer("Игрок не найден.", show_alert=True)
            return
        await query.answer()
        await ensure_greenhouse(uid)
        gh = await get_greenhouse(uid)
        selected = gh.get("selected_crop") or "картошка"
        await handle_grow(update, user2, ["вырастить", selected, str(qty)])

    elif data.startswith("gh_select_"):
'''
if marker not in s:
    raise SystemExit('greenhouse callback marker not found')
s = s.replace(marker, callback, 1)
p.write_text(s, encoding='utf-8')

p = Path('база_данных/теплица.py')
s = p.read_text(encoding='utf-8').replace('await update.message.reply_text(', 'await update.effective_message.reply_text(')
p.write_text(s, encoding='utf-8')
