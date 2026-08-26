# -*- coding: utf-8 -*-
import asyncio
import html
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
import aiosqlite

from настройки import (
    BOT_TOKEN, DB_PATH, ADMIN_IDS, ROOMS_DATA, GAME_COOLDOWNS, ROOM_UPGRADE_COOLDOWNS,
    PROMO_CODES, RP_COMMANDS, CROPS, CROP_FORMS, CROP_FORMS_ACC,
    OCHKO_GAMES, HO_GAMES, MINE_RESOURCES,
)
from вспомогательные.вспомогательные_функции import (
    fmt_smart, user_link, safe_nick, check_cooldown, set_cooldown,
    get_balance_limit, get_current_income, get_vip_transfer_limit,
    get_room_upgrade_cd, parse_bet, get_vip_water_limit,
    card_value, hand_value, hand_str,
)
from вспомогательные.проверки import require_bunker, has_room, user_exists
from вспомогательные.сообщения import build_bunker_text, build_room_text, build_top_text, ho_board_text
from база_данных.база import (
    init_db, get_user, get_rooms, get_room_level, get_total_income, create_bunker,
)
from база_данных.бункер import do_room_upgrade, queue_refill_job, passive_income_job, handle_repair_bunker
from база_данных.пользователи import (
    handle_balance, handle_change_nick, handle_rating, handle_buy_rating, handle_sell_rating,
    handle_ref, handle_bonus, handle_promo, handle_donate, handle_donate_rate, handle_statuses,
    handle_limits, cmd_balance_slash, cmd_ref_slash, cmd_bonus_slash, cmd_donation_slash, cmd_rating_slash,
)
from база_данных.теплица import (
    handle_my_greenhouse, handle_greenhouse_info, handle_greenhouse_rate,
    handle_grow, handle_sell_crop, water_refill_job,
    ensure_greenhouse, get_greenhouse, get_available_crops,
)
from база_данных.шахта import (
    handle_mine_info, handle_my_mine, handle_mine_rate,
    handle_dig, handle_buy_pickaxe, handle_sell_mine_resource,
    get_mine, DIG_PENDING,
)
from клавиатуры.общие import no_bunker_keyboard, back_keyboard, donate_keyboard
from клавиатуры.главное_меню import help_main_keyboard
from клавиатуры.бункер import room_keyboard, top_keyboard
from клавиатуры.активности import handle_rp_list, handle_rp_action
from сервисы.экономика import (
    handle_barrels_info, handle_buy_barrel, handle_open_barrel,
    handle_ochko_start, handle_ho_start, ho_check_winner, ho_keyboard,
    handle_fuel, fuel_consume_job, cmd_cases_slash,
)
from сервисы.комнаты import cmd_room, cmd_rooms_list, cmd_let_in, cmd_buy_room, cmd_rooms_command
from сервисы.пользователи import cmd_start, cmd_help, cmd_bunker, handle_top, cmd_top_slash

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    text = raw.lower()

    # ── No bunker commands ───────────────────────────────────────────────────
    if text == "помощь":
        await cmd_help(update, context)
        return

    if text == "создать бункер":
        uid = update.effective_user.id
        if await user_exists(uid):
            await update.message.reply_text("У вас уже есть бункер! Посмотрите его командой Мой бункер")
            return
        uname = update.effective_user.first_name or "Игрок"
        await create_bunker(uid, uname)
        await update.message.reply_text("Бункер успешно создан!\nПосмотреть его можно командой Мой бункер")
        return

    uid = update.effective_user.id

    # ── Admin commands ───────────────────────────────────────────────────────
    if uid in ADMIN_IDS:
        parts = raw.split()

        selected_reward_t = context.user_data.get("admin_promo_reward_type")
        if selected_reward_t and parts and parts[0].lower() != "добпромо":
            if len(parts) < 2:
                await update.message.reply_text("Формат: <code>код сумма [использований]</code>", parse_mode=ParseMode.HTML)
                return
            promo_code_new = parts[0].lower()
            try:
                reward_a = int(parts[1])
                uses = int(parts[2]) if len(parts) >= 3 else 1
            except ValueError:
                await update.message.reply_text("Сумма и количество использований должны быть числами.")
                return
            if reward_a <= 0 or uses <= 0:
                await update.message.reply_text("Сумма и количество использований должны быть больше нуля.")
                return
            PROMO_CODES[promo_code_new] = {"reward_type": selected_reward_t, "amount": reward_a, "uses_left": uses}
            context.user_data.pop("admin_promo_reward_type", None)
            await update.message.reply_text(
                f"✅ Промокод '{promo_code_new}' добавлен: {selected_reward_t} ×{reward_a}.\n"
                f"👥 Использований: {uses} (один пользователь — только 1 раз).",
                parse_mode=ParseMode.HTML
            )
            return

        if parts[0].lower() == "выдать" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            target_id = int(parts[1])
            amount = int(parts[2])
            if not await user_exists(target_id):
                await update.message.reply_text("Игрок не найден.")
                return
            target_rooms = await get_rooms(target_id)
            limit = get_balance_limit(target_rooms)
            target_user = await get_user(target_id)
            current = target_user["balance"]
            give = min(amount, limit - current)
            if give <= 0:
                await update.message.reply_text(f"У игрока уже максимальный баланс ({fmt_smart(limit)} кр.)")
                return
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (give, target_id))
                await db.commit()
            await update.message.reply_text(f"✅ Выдано {fmt_smart(give)} кр. игроку {target_id}.")
            return

        if parts[0].lower() == "выдатьвип" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            target_id = int(parts[1])
            vip_level = int(parts[2])
            if vip_level < 0 or vip_level > 4:
                await update.message.reply_text("Уровень VIP должен быть от 0 до 4.")
                return
            if not await user_exists(target_id):
                await update.message.reply_text("Игрок не найден.", parse_mode=ParseMode.HTML)
                return
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET vip = ? WHERE user_id = ?", (vip_level, target_id))
                await db.commit()
            await update.message.reply_text(f"✅ Выдан VIP{vip_level} игроку {target_id}.")
            return

        if parts[0].lower() == "статус" and len(parts) >= 3 and parts[1].isdigit():
            target_id = int(parts[1])
            status_text = " ".join(parts[2:])
            if not await user_exists(target_id):
                await update.message.reply_text("Игрок не найден.")
                return
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET custom_status = ? WHERE user_id = ?", (status_text, target_id))
                await db.commit()
            await update.message.reply_text(f"✅ Статус игрока {target_id} установлен: {status_text}")
            return

        if parts[0].lower() == "убратьстатус" and len(parts) == 2 and parts[1].isdigit():
            target_id = int(parts[1])
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET custom_status = NULL WHERE user_id = ?", (target_id,))
                await db.commit()
            await update.message.reply_text(f"✅ Статус игрока {target_id} убран.")
            return

        if parts[0].lower() == "кач" and len(parts) == 4 and parts[1].isdigit() and parts[2].isdigit() and parts[3].isdigit():
            target_id = int(parts[1])
            room_num = int(parts[2])
            levels = int(parts[3])
            if not await user_exists(target_id):
                await update.message.reply_text("Игрок не найден.")
                return
            if not await has_room(target_id, room_num):
                await update.message.reply_text(f"У игрока нет комнаты №{room_num}.", parse_mode=ParseMode.HTML)
                return
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?",
                                 (levels, target_id, room_num))
                await db.commit()
            new_level = await get_room_level(target_id, room_num)
            new_income = get_current_income(room_num, new_level)
            await update.message.reply_text(
                f"✅ Комната №{room_num} прокачана до {new_level} ур.\n"
                f"💵 Доход: {fmt_smart(new_income)} кр/час"
            , parse_mode=ParseMode.HTML)
            return

        if parts[0].lower() == "добпромо":
            if len(parts) == 1:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Крышки", callback_data="admin_promo_type_coins"), InlineKeyboardButton("🍾 Бутылки", callback_data="admin_promo_type_bottles")],
                    [InlineKeyboardButton("⭐️ Опыт", callback_data="admin_promo_type_exp"), InlineKeyboardButton("🏆 Рейтинг", callback_data="admin_promo_type_rating")],
                    [InlineKeyboardButton("🪙 BB-coins", callback_data="admin_promo_type_bbcoins")],
                ])
                await update.message.reply_text("Какую выберете?", reply_markup=kb)
                return
            if len(parts) < 4:
                await update.message.reply_text("Формат: <code>ДобПромо код тип сумма [использований]</code>\nЕсли количество использований не указать, промокод можно использовать 1 раз.", parse_mode=ParseMode.HTML)
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
            await update.message.reply_text(f"✅ Промокод '{promo_code_new}' добавлен: {reward_t} ×{reward_a}.\n👥 Использований: {uses} (один пользователь — только 1 раз).", parse_mode=ParseMode.HTML)
            return

    if not await user_exists(uid):
        await update.message.reply_text(
            "Сначала создайте Бункер чтобы пользоваться ботом с командой Создать бункер, либо по кнопке ниже",
            reply_markup=no_bunker_keyboard()
        , parse_mode=ParseMode.HTML)
        return

    user = await get_user(uid)

    # Бункер
    if text in ["бункер", "б", "мой бункер"]:
        t = await build_bunker_text(uid)
        await update.message.reply_text(t, parse_mode=ParseMode.HTML)
        return

    # Список комнат
    if text in ["список комнат", "комнаты"]:
        await cmd_rooms_list(update, context)
        return
    
    if text == "бензин":
        await handle_fuel(update, user)
        return
    # Купить комнату
    if text.startswith("купить комнату"):
        parts = text.split()
        room_num_buy = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
        await cmd_buy_room(update, context, room_num_buy)
        return

    # Впустить
    if text.startswith("впустить"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            await cmd_let_in(update, context, int(parts[1]))
        else:
            await cmd_let_in(update, context, None)
        return

    # Комната К N
    room_num = None
    if text.startswith("к ") or text.startswith("комната "):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            room_num = int(parts[1])
    elif text.startswith("к") and len(text) > 1 and text[1:].isdigit():
        room_num = int(text[1:])
    if room_num and 1 <= room_num <= 19:
        await cmd_room(update, context, room_num)
        return

    # Рейтинг
    if text == "рейтинг":
        await handle_rating(update, user)
        return

    if text.startswith("купить рейтинг"):
        parts = text.split()
        if len(parts) >= 3 and parts[2].isdigit():
            await handle_buy_rating(update, user, int(parts[2]))
        else:
            await update.message.reply_text("Укажите количество: Купить рейтинг [число]")
        return

    if text.startswith("продать рейтинг"):
        parts = text.split()
        if len(parts) >= 3 and parts[2].isdigit():
            await handle_sell_rating(update, user, int(parts[2]))
        else:
            await update.message.reply_text("Укажите количество: Продать рейтинг [число]")
        return

    # Сменить ник
    if text.startswith("сменить ник "):
        new_nick = raw[len("сменить ник "):].strip()
        if new_nick:
            await handle_change_nick(update, user, new_nick)
        else:
            await update.message.reply_text("Укажите новый ник: Сменить ник [ник]")
        return

    # ТОП
    if text == "топ":
        await handle_top(update, user, "rating")
        return
    if text == "топ рейтинг":
        await handle_top(update, user, "rating")
        return
    if text == "топ доход":
        await handle_top(update, user, "income")
        return
    if text in ["топ крышки", "топ крышек"]:
        await handle_top(update, user, "coins")
        return
    if text == "топ теплица":
        await handle_top(update, user, "greenhouse")
        return
    if text == "топ пустошь":
        await handle_top(update, user, "wasteland")
        return
    if text in ["топ гильдии", "топ гильдий"]:
        await handle_top(update, user, "guilds")
        return
    if text in ["топ жители", "топ жителей"]:
        await handle_top(update, user, "residents")
        return
    if text in ["топ бутылки", "топ бутылок"]:
        await handle_top(update, user, "bottles")
        return

    # Баланс бб
    if text in ["бб", "bb"]:
        await handle_balance(update, user)
        return

    # Донат
    if text in ["донат", "донат команды"]:
        await handle_donate(update, user)
        return
    if text == "донат курс":
        await handle_donate_rate(update, user)
        return

    # Статусы
    if text == "статусы":
        await handle_statuses(update, user)
        return

    # Промокод
# Промокод
    if text == "промокод" or text == "промо":
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(user['user_id'], user['username'])}, этой командой можно использовать промокод!\n"
            f"Следите за новостным каналом чтобы не пропускать их\n\n"
            f"Пример: <code>Промо [название промокода]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    if text.startswith("промокод ") or text.startswith("промо "):
        parts = raw.split(maxsplit=1)
        if len(parts) == 2:
            await handle_promo(update, user, parts[1].strip())
        else:
            await update.message.reply_text("Укажите промокод: Промо [код]")
        return

# Обменять бутылки
    if text.startswith("обменять бутылки"):
        parts = text.split()
        if len(parts) >= 3 and parts[2].isdigit():
            amount = int(parts[2])
            bottles = user["bottles"]
            if bottles < amount:
                await update.message.reply_text(f"{user_link(user['user_id'], user['username'])}, у тебя недостаточно бутылок!", parse_mode=ParseMode.HTML)
                return
            coins = int(amount * 10000 * (bottles % 1 if amount == int(bottles) else 1))
            # Считаем точно: amount целых бутылок, но у юзера могут быть дробные
            actual_bottles = min(amount, bottles)
            coins_earned = int(actual_bottles * 10000)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET bottles = bottles - ?, balance = balance + ? WHERE user_id = ?",
                                 (actual_bottles, coins_earned, user['user_id']))
                await db.commit()
            await update.message.reply_text(
                f"🙎‍♂️ {user_link(user['user_id'], user['username'])}, ты успешно конвертировал(-а) {amount} 🍾 в {fmt_smart(coins_earned)} крышек 💰"
            , parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"{user_link(user['user_id'], user['username'])}, этой командой можно конвертировать свои бутылки в крышки!\nКурс: 1 бутылка -> 10.000 крышек\n\nПример: Обменять бутылки [кол-во бутылок]", parse_mode=ParseMode.HTML)
        return
    

    # Реф
    if text in ["реф", "рефералка", "ref"]:
        await handle_ref(update, user)
        return

    # Лимиты
    if text == "лимиты":
        await handle_limits(update, user)
        return

    # РП команды список
    if text in ["рп команды", "рп"]:
        await handle_rp_list(update, user)
        return

    # РП действие: <команда> @ник или <команда> имя
    for action in RP_COMMANDS:
        if text == action or text.startswith(action + " ") or text.startswith(action + "@"):
            await handle_rp_action(update, user, action)
            return

# ── Передать деньги ───────────────────────────────────────────────────────
    if text.startswith("дать "):
        parts_raw2 = raw.split()
        if len(parts_raw2) >= 2:
            try:
                amount_give = int(parts_raw2[1])
            except:
                amount_give = None
            reply_msg = update.message.reply_to_message
            if amount_give and amount_give > 0:
                if not reply_msg:
                    await update.message.reply_text(
                        f"{user_link(uid, user['username'])}, ответь на сообщение игрока, которому хочешь передать крышки!",
                        parse_mode=ParseMode.HTML
                    )
                    return
                target = reply_msg.from_user
                if target.is_bot:
                    await update.message.reply_text(
                        f"{user_link(uid, user['username'])}, нельзя передавать крышки боту!",
                        parse_mode=ParseMode.HTML
                    )
                    return
                if target.id == uid:
                    await update.message.reply_text("Нельзя передавать крышки самому себе!", parse_mode=ParseMode.HTML)
                    return
                vip = user.get("vip", 0)
                transfer_limit = get_vip_transfer_limit(vip)
                if amount_give > transfer_limit:
                    await update.message.reply_text(
                        f"{user_link(uid, user['username'])}, вы превысили лимит!\n"
                        f"Максимум для вашего статуса: {fmt_smart(transfer_limit)} кр.",
                        parse_mode=ParseMode.HTML
                    )
                    return
                if user["balance"] < amount_give:
                    await update.message.reply_text(
                        f"{user_link(uid, user['username'])}, у тебя недостаточно крышек!",
                        parse_mode=ParseMode.HTML
                    )
                    return
                if not await user_exists(target.id):
                    await update.message.reply_text("Этот игрок ещё не создал бункер!", parse_mode=ParseMode.HTML)
                    return
                target_user_db = await get_user(target.id)
                target_rooms = await get_rooms(target.id)
                target_limit = get_balance_limit(target_rooms)
                if target_user_db["balance"] >= target_limit:
                    await update.message.reply_text("У этого игрока уже максимальный баланс!", parse_mode=ParseMode.HTML)
                    return
                give_actual = min(amount_give, target_limit - target_user_db["balance"])
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (give_actual, uid))
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (give_actual, target.id))
                    await db.commit()
                target_name = target_user_db["username"] or target.first_name or "Игрок"
                await update.message.reply_text(
                    f"🙎‍♂️ {user_link(uid, user['username'])} передал(-а) {fmt_smart(give_actual)} кр. игроку {user_link(target.id, target_name)}!",
                    parse_mode=ParseMode.HTML
                )
                return
        await update.message.reply_text(
            f"Пример: ответь на сообщение игрока и напиши <code>Дать 1000</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # ── Бочки ────────────────────────────────────────────────────────────────
    if text == "бочки":
        await handle_barrels_info(update, user)
        return

    if text.startswith("купить бочку"):
        parts_b = raw.split()  # не lower() чтобы числа сохранились
        await handle_buy_barrel(update, user, parts_b)
        return

    if text.startswith("открыть бочку"):
        parts_b = raw.split()  # убираем .lower()
        await handle_open_barrel(update, user, parts_b)
        return

    # ── Починить бункер ───────────────────────────────────────────────────────
    if text == "починить бункер":
        await handle_repair_bunker(update, user)
        return

    # ── Теплица ───────────────────────────────────────────────────────────────
    if text in ["моя теплица", "теплица"]:
        await handle_my_greenhouse(update, user)
        return

    if text == "теплица инфо":
        await handle_greenhouse_info(update, user)
        return

    if text == "курс теплица":
        await handle_greenhouse_rate(update, user)
        return

    if text.startswith("вырастить"):
        parts_g = raw.split()
        await handle_grow(update, user, parts_g)
        return

    # Продать культуру (теплица)
# Продать культуру (теплица)
    if text.startswith("продать "):
        parts_s = raw.split()
        if len(parts_s) >= 2:
            raw_crop_s = parts_s[1].lower()
            crop_normalized = CROP_FORMS.get(raw_crop_s, raw_crop_s)
            if crop_normalized in CROPS:
                parts_s[1] = crop_normalized
                await handle_sell_crop(update, user, parts_s)
                return

    # ── Шахта ─────────────────────────────────────────────────────────────────
    if text in ["моя шахта", "шахта"]:
        await handle_my_mine(update, user)
        return

    if text == "шахта инфо":
        await handle_mine_info(update, user)
        return

    if text == "курс шахта":
        await handle_mine_rate(update, user)
        return

    if text == "копать":
        await handle_dig(update, user)
        return

    if text.startswith("купить кирку"):
        parts_pk = text.split()
        if len(parts_pk) >= 3 and parts_pk[2].isdigit():
            await handle_buy_pickaxe(update, user, int(parts_pk[2]))
        else:
            await update.message.reply_text(
                f"Пример: <code>Купить кирку [1/2/3]</code>\nШахта инфо — для просмотра цен",
                parse_mode=ParseMode.HTML
            )
        return

    # Продать ресурс шахты
    if text.startswith("продать "):
        parts_sm = raw.split()
        if len(parts_sm) >= 2:
            res_name = parts_sm[1]
            qty_str = parts_sm[2] if len(parts_sm) >= 3 else "всё"
            handled = await handle_sell_mine_resource(update, user, res_name, qty_str)
            if handled:
                return

    # ── Очко ──────────────────────────────────────────────────────────────────
    if text.startswith("очко ") or text.startswith("21 "):
        parts_o = raw.split()
        if len(parts_o) >= 2:
            bet = parse_bet(parts_o[1], user["balance"])
            if bet > 0:
                await handle_ochko_start(update, user, bet)
            else:
                await update.message.reply_text(
                    f"Пример: <code>Очко [ставка]</code> или <code>21 [ставка]</code>",
                    parse_mode=ParseMode.HTML
                )
        return
    
    if text.startswith("купить кирку") or text.startswith("купить каменную кирку") or \
       text.startswith("купить железную кирку") or text.startswith("купить алмазную кирку"):
        name_map = {"каменную": 1, "железную": 2, "алмазную": 3}
        parts_pk = text.split()
        num = None
        for word, n in name_map.items():
            if word in parts_pk:
                num = n
                break
        if num is None and len(parts_pk) >= 3 and parts_pk[2].isdigit():
            num = int(parts_pk[2])
        if num:
            await handle_buy_pickaxe(update, user, num)
        else:
            await update.message.reply_text(
                f"Пример: <code>Купить кирку [1/2/3]</code> или <code>Купить железную кирку</code>",
                parse_mode=ParseMode.HTML
            )
        return
# ── ИГРЫ ──────────────────────────────────────────────────────────────────

    async def check_bet(bet_str: str) -> int:
        b = parse_bet(bet_str, user["balance"])
        return b

    # Казино
    # Казино
    if text.startswith("казино"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Казино [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек. перед следующей игрой!")
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        vip = user.get("vip", 0)
        # Мультипликаторы: 0x, -0.25x(возврат 75%), -0.5x(возврат 50%), 1x, 2x, 5x, 10x
        outcomes = [
            (0,    "😵 Проигрыш! x0 — потерял всё."),
            (-0.25,"😬 Неудача! x-0.25 — потеря 25%."),
            (-0.5, "💔 Плохо! x-0.5 — потеря 50%."),
            (1,    "😐 Тебе выпало x1! Возврат ставки."),
            (2,    "💰 Тебе выпало x2! Выигрыш х2!"),
            (5,    "🎉 Тебе выпало x5! Крупный выигрыш!"),
            (10,   "🔥 ДЖЕКПОТ x10! Невероятно!"),
        ]
        weights_map = {
            0: [30, 20, 15, 20, 10, 4, 1],
            1: [27, 18, 13, 22, 12, 6, 2],
            2: [25, 16, 12, 23, 13, 8, 3],
            3: [22, 14, 10, 24, 15, 11, 4],
            4: [20, 12, 8,  25, 17, 13, 5],
        }
        w = weights_map.get(vip, weights_map[0])
        mult, desc = random.choices(outcomes, weights=w, k=1)[0]
        if mult <= 0:
            loss = int(bet * abs(mult)) if mult != 0 else bet
            win_return = bet - loss
            change = -loss
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (loss, uid))
                await db.commit()
            if mult == 0:
                result_line = f"😵 Тебе выпало x0! Потерял {fmt_smart(bet)} кр."
            else:
                result_line = f"Тебе выпало x{abs(mult)}! Твой проигрыш составил {fmt_smart(loss)} кр."
        else:
            win = int(bet * mult)
            change = win - bet
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
                await db.commit()
            result_line = f"Тебе выпало x{mult}! Твой выигрыш составил {fmt_smart(change)} кр!" if change > 0 else f"Тебе выпало x{mult}! Ставка возвращена."
        set_cooldown(uid)
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🎱 {user_link(uid, user['username'])}\n"
            f"💰 {result_line}\n"
            f"· · · · · · · · · · · · · · ·\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            f"📊 Итог: {sign}{fmt_smart(change)} кр.",
            parse_mode=ParseMode.HTML
        )
        return

    # Спин (слоты)
    if text.startswith("спин"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Спин [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        slots = ["🍒", "🍋", "🍊", "🍇", "⭐️", "💎", "7️⃣"]
        reel = [random.choice(slots) for _ in range(3)]
        if reel[0] == reel[1] == reel[2]:
            mult = {"7️⃣": 10, "💎": 7, "⭐️": 5}.get(reel[0], 3)
            win = bet * mult
            desc = f"🎉 Три в ряд! x{mult}"
        elif reel[0] == reel[1] or reel[1] == reel[2]:
            win = int(bet * 1.5)
            desc = "😊 Два в ряд! x1.5"
        else:
            win = 0
            desc = "❌ Не повезло!"
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🎰 {user_link(uid, user['username'])}\n"
            f"[ {' | '.join(reel)} ]\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            f"{desc}\n"
            f"📊 Итог: {sign}{fmt_smart(change)} кр.",
            parse_mode=ParseMode.HTML
        )
        return

    # Рулетка
    if text.startswith("рулетка"):
        parts_g = raw.split()
        if len(parts_g) < 3:
            await update.message.reply_text(f"Пример: <code>Рулетка [число/красное/чётное/1-12] [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек.")
            return
        bet_type = parts_g[1].lower()
        bet = parse_bet(parts_g[2], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        set_cooldown(uid)
        num = random.randint(0, 36)
        red_nums = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        win = 0
        if bet_type.isdigit() and int(bet_type) == num:
            win = bet * 35
        elif bet_type in ("красное", "red") and num in red_nums:
            win = bet * 2
        elif bet_type in ("чёрное", "black") and num not in red_nums and num != 0:
            win = bet * 2
        elif bet_type in ("чётное", "even") and num % 2 == 0 and num != 0:
            win = bet * 2
        elif bet_type in ("нечётное", "odd") and num % 2 == 1:
            win = bet * 2
        elif bet_type == "1-12" and 1 <= num <= 12:
            win = bet * 3
        elif bet_type == "13-24" and 13 <= num <= 24:
            win = bet * 3
        elif bet_type == "25-36" and 25 <= num <= 36:
            win = bet * 3
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        color = "🟢" if num == 0 else ("🔴" if num in red_nums else "⚫️")
        result_text = f"✅ Твой выигрыш составил <b>{fmt_smart(change)}</b> кр.!" if change > 0 else "🛑 Ты проиграл(-а)! Попытай удачу в следующий раз 😣"
        await update.message.reply_text(
            f"{user_link(uid, user['username'])}\n🖲 Выпало - {num} {color}\n{result_text}",
            parse_mode=ParseMode.HTML
        )
        return

    # Кубик
    if text.startswith("кубик"):
        parts_g = raw.split()
        if len(parts_g) < 3 or not parts_g[1].isdigit():
            await update.message.reply_text(f"Пример: <code>Кубик [число 1-6] [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек.")
            return
        guess = int(parts_g[1])
        bet = parse_bet(parts_g[2], user["balance"])
        if guess < 1 or guess > 6:
            await update.message.reply_text("Число от 1 до 6!", parse_mode=ParseMode.HTML)
            return
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        set_cooldown(uid)
        rolled = random.randint(1, 6)
        if rolled == guess:
            win = bet * 5
        else:
            win = 0
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        result_text = f"✅ Твой выигрыш составил <b>{fmt_smart(change)}</b> кр.!" if change > 0 else "🛑 Ты проиграл(-а)! Попытай удачу в следующий раз 😣"
        await update.message.reply_text(
            f"{user_link(uid, user['username'])}\n🎲 Выпало - {rolled}\n{result_text}",
            parse_mode=ParseMode.HTML
        )
        return

    # Стаканчик
    if text.startswith("стаканчик"):
        parts_g = raw.split()
        if len(parts_g) < 2 or not parts_g[1].isdigit() or int(parts_g[1]) not in (1,2,3):
            await update.message.reply_text(f"Пример: <code>Стаканчик [1, 2 или 3]</code>", parse_mode=ParseMode.HTML)
            return
        guess = int(parts_g[1])
        correct = random.randint(1, 3)
        cups = {1:"🥛",2:"🥛",3:"🥛"}
        cups[correct] = "🏆"
        if guess == correct:
            desc = f"✅ Правильно! Шарик был под стаканом {correct}."
            bonus = 1000
        else:
            desc = f"❌ Неверно. Шарик был под стаканом {correct}."
            bonus = 0
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (bonus, uid))
            await db.commit()
        await update.message.reply_text(
            f"🥛 {user_link(uid, user['username'])}\n"
            f"1:{cups[1]}  2:{cups[2]}  3:{cups[3]}\n"
            f"{desc}" + (f"\n+{fmt_smart(bonus)} кр." if bonus else ""),
            parse_mode=ParseMode.HTML
        )
        return

    # Орёл/Решка
    if text.startswith("орёл") or text.startswith("решка") or text.startswith("орел"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Орёл [ставка]</code> или <code>Решка [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        guess = "орёл" if text.startswith("орёл") or text.startswith("орел") else "решка"
        result = random.choice(["орёл", "решка"])
        emojis = {"орёл":"🦅","решка":"🪙"}
        if guess == result:
            win = bet * 2
            desc = f"✅ {emojis[result]} Правильно! x2"
        else:
            win = 0
            desc = f"❌ {emojis[result]} Не угадал(-а)."
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🪙 {user_link(uid, user['username'])}\n"
            f"💸 Ставка: {fmt_smart(bet)} кр. на {emojis[guess]}\n"
            f"{desc}\n"
            f"📊 Итог: {sign}{fmt_smart(change)} кр.",
            parse_mode=ParseMode.HTML
        )
        return

    # Боулинг
    # Боулинг
    if text.startswith("боулинг"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Боулинг [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек.")
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        set_cooldown(uid)
        dice_msg = await update.message.reply_dice(emoji="🎳")
        await asyncio.sleep(3)
        pins = dice_msg.dice.value
        if pins == 6:
            win, desc = bet * 3, "🎳 СТРАЙК! x3"
        elif pins == 5:
            win, desc = int(bet * 1.5), "🎳 Отличный бросок! x1.5"
        elif pins in (3, 4):
            win, desc = bet, f"😐 {pins}/6. x1 (возврат)"
        else:
            win, desc = 0, f"❌ {pins}/6. x0"
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🎳 {user_link(uid, user['username'])}, {desc}\n"
            f"· · · · · · · · · · · · · · ·\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            + (f"🎉 Выигрыш: {fmt_smart(win)} кр." if change > 0 else f"📊 Итог: {sign}{fmt_smart(change)} кр."),
            parse_mode=ParseMode.HTML
        )
        return

    # Баскетбол
    # Баскетбол
    if text.startswith("баскетбол"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Баскетбол [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек.")
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        set_cooldown(uid)
        dice_msg = await update.message.reply_dice(emoji="🏀")
        await asyncio.sleep(3)
        roll = dice_msg.dice.value
        if roll == 5:
            win, desc = bet * 2, "🏀 Попал в кольцо! x2"
        elif roll in (3, 4):
            win, desc = int(bet * 1.2), "🏀 Рикошет и попал! x1.2"
        else:
            win, desc = 0, "❌ Промах мимо кольца! x0"
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🏀 {user_link(uid, user['username'])}, {desc}\n"
            f"· · · · · · · · · · · · · · ·\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            + (f"🎉 Выигрыш: {fmt_smart(win)} кр." if change > 0 else f"📊 Итог: {sign}{fmt_smart(change)} кр."),
            parse_mode=ParseMode.HTML
        )
        return

    # Дартс
    # Дартс
    if text.startswith("дартс"):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Дартс [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        cd = check_cooldown(uid)
        
        if cd:
            await update.message.reply_text(f"⏳ Подождите {cd} сек.")
            return
        bet = parse_bet(parts_g[1], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        set_cooldown(uid)
        dice_msg = await update.message.reply_dice(emoji="🎯")
        await asyncio.sleep(3)
        roll = dice_msg.dice.value
        if roll == 6:
            win, mult, desc = bet * 10, "x10", "меткость твоё второе имя! БУЛЛСАЙ! 🎯"
        elif roll == 5:
            win, mult, desc = bet * 5, "x5", "отличный бросок! 🎯"
        elif roll == 4:
            win, mult, desc = bet * 2, "x2", "попал! x2 🎯"
        elif roll == 3:
            win, mult, desc = bet, "x1", "попал рядом с центром. x1 🤨"
        else:
            win, mult, desc = 0, "x0", "промахнулся! x0 😱"
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        if change > 0:
            result_line = f"🎉 Выигрыш: {fmt_smart(win)} кр."
        elif change == 0:
            result_line = f"😐 Ставка возвращена."
        else:
            result_line = f"📊 Потеря: {fmt_smart(bet)} кр."
        await update.message.reply_text(
            f"🎯 {user_link(uid, user['username'])}, {desc}\n"
            f"· · · · · · · · · · · · · · ·\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            f"{result_line}",
            parse_mode=ParseMode.HTML
        )
        return
    
# Крестики-нолики
    if text.startswith("хо ") or text == "играть хо":
        if text == "играть хо":
            await update.message.reply_text(f"Пример: <code>хо [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        parts_ho = raw.split()
        bet = parse_bet(parts_ho[1], user["balance"])
        if bet > 0:
            await handle_ho_start(update, user, bet)
        else:
            await update.message.reply_text(f"Пример: <code>хо [ставка]</code>", parse_mode=ParseMode.HTML)
        return
    
    # Ежедневный бонус
    if text in ["ежедневный бонус", "бонус"]:
        await handle_bonus(update, user)
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = query.from_user.id

    if data.startswith("admin_promo_type_"):
        if uid not in ADMIN_IDS:
            await query.answer("Нет доступа.", show_alert=True)
            return
        reward_t = data[len("admin_promo_type_"):].lower()
        if reward_t not in {"coins", "bottles", "rating", "bbcoins", "exp"}:
            await query.answer("Неизвестный тип награды.", show_alert=True)
            return
        context.user_data["admin_promo_reward_type"] = reward_t
        await query.answer()
        labels = {"coins": "💰 крышки", "bottles": "🍾 бутылки", "exp": "⭐️ опыт", "rating": "🏆 рейтинг", "bbcoins": "🪙 BB-coins"}
        await query.message.reply_text(
            f"Выбрано: {labels[reward_t]}.\n"
            "Теперь отправьте: <code>код сумма [использований]</code>\n"
            "Если количество использований не указать, будет 1. Один пользователь сможет использовать промокод только один раз.",
            parse_mode=ParseMode.HTML
        )
        return

    if data == "create_bunker":
        await query.answer()
        if await user_exists(uid):
            await query.message.reply_text("У вас уже есть бункер! Посмотрите его командой Мой бункер")
            return
        uname = query.from_user.first_name or "Игрок"
        await create_bunker(uid, uname)
        await query.message.reply_text("Бункер успешно создан!\nПосмотреть его можно командой Мой бункер")

    elif data == "help_back":
        await query.answer()
        await cmd_help(update, context)

    elif data == "help_main":
        await query.answer()
        user = await get_user(uid)
        username = user["username"] if user else (query.from_user.first_name or "Игрок")
        text = (
            f"🙎‍♂️ {user_link(user['user_id'], username)}, меню общей информации\n\n"
            "📜 Команды -\n"
            "   🏚️ Создать бункер\n"
            "   🏫 <code>Мой бункер</code> (Бункер, Б, Бб)\n"
            "   🏠 <code>Комната</code> (К)\n"
            "   🏘 <code>Список комнат</code>\n"
            "   🙎‍♂️ <code>Впустить</code>\n"
            "   💰 <code>Купить комнату</code>\n"
            "   🏆 <code>Рейтинг</code> / <code>Купить рейтинг</code> / <code>Продать рейтинг</code>\n"
            "   🔝 <code>Топ</code> | <code>Топ теплица</code> | <code>Топ крышки</code>\n"
            "   💎 <code>Донат</code> / <code>Донат курс</code>\n"
            "   🌈 <code>Статусы</code>\n"
            "   🎁 <code>Промокод</code>\n"
            "   👨‍👨‍👦‍👦 <code>Реф</code>\n"
            "   📝 <code>Сменить ник</code> [ник]\n"
            "   ⏳ <code>Лимиты</code>\n"
            "   🏌️‍♀️ <code>РП команды</code>\n"
            "   🎉 <code>Ежедневный бонус</code>\n"
        )
        await query.message.edit_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "help_games":
        await query.answer()
        user = await get_user(uid)
        username = user["username"] if user else (query.from_user.first_name or "Игрок")
        text = (
            f"🙎‍♂️ {user_link(user['user_id'], username)}, меню развлечений\n\n"
            "🎉 Игры -\n"
            "   🎱 <code>Казино</code> [ставка]\n"
            "   🎰 <code>Спин</code> [ставка]\n"
            "   🎮 <code>Рулетка</code> [число/красное/чётное/1-12] [ставка]\n"
            "   🎲 <code>Кубик</code> [число] [ставка]\n"
            "   🥛 <code>Стаканчик</code> [1, 2, 3]\n"
            "   🪙 <code>Орёл/Решка</code> [ставка]\n"
            "   🎳️ <code>Боулинг</code> [ставка]\n"
            "   🏀 <code>Баскетбол</code> [ставка]\n"
            "   🎯 <code>Дартс</code> [ставка]\n"
            "   ♠️ <code>Очко</code> [ставка]\n"
            "   ❌⭕️ Играть <code>хо</code>"
        )
        await query.message.edit_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "help_activities":
        await query.answer()
        user = await get_user(uid)
        username = user["username"] if user else (query.from_user.first_name or "Игрок")
        text = (
            f"🙎‍♂️ {user_link(user['user_id'], username)}, меню активностей\n\n"
            "📜 Команды\nОбщее\n"
            "   🛢 <code>Бочки</code>\n   💰 <code>Купить бочку</code>\n   🔥 <code>Открыть бочку</code>\n"
            "   ⛽️ <code>Бензин</code>\n   🔧 <code>Починить бункер</code>\n\n"
            "Теплица\n   🌅 <code>Моя теплица</code>\n   📝 <code>Теплица инфо</code>\n"
            "   📈 <code>Курс теплица</code>\n   🪴 <code>Вырастить</code>\n   💸 <code>Продать картошку</code>\n\n"
            "Шахта\n   🚂 <code>Моя шахта</code>\n   📝 <code>Шахта инфо</code>\n   💸 <code>Продать уголь</code>\n\n"
            "Сад\n   🌱 <code>Купить саженцы</code>\n   🏡 <code>Мой сад</code>\n   🌿 <code>Улучшить сад</code>\n\n"
            "Пустошь\n   🔎 <code>Исследовать пустошь</code>\n   🏜️ <code>Пустошь</code>\n"
            "   ⏳ <code>История пустоши</code>\n   🔫 <code>Купить оружие</code>\n   🧪 <code>Купить стимуляторы</code>\n"
            "   🚘 <code>Авто инфо</code>\n   🚘 <code>Гараж</code>\n\n"
            "Гильдии\n   🏰 <code>Создать гильдию</code>\n   💼 <code>Моя гильдия</code>\n"
            "   👋 <code>Покинуть гильдию</code>\n   💌 <code>Пригласить в гильдию</code>\n   🚪 <code>Исключить из гильдии</code>\n"
            "   💰 <code>Пополнить банки</code>\n   🧡 <code>Пополнить бутылки</code>\n   ⚔️ <code>Купить атаку</code>\n"
            "   🛡️ <code>Купить защиту</code>\n   🍾 <code>Выдать бутылки</code>\n   🔄 <code>Обменять бутылки</code>\n"
            "   ⚔️ <code>Напасть на гильдию</code>\n   🐉 <code>Атаковать босса</code>\n   💬 <code>Чат гильдии</code>\n"
            "   📊 <code>Топ гильдий</code>\n   🪄 <code>Назначить заместителя</code>\n   ❌ <code>Снять заместителя</code>"
        )
        await query.message.edit_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "help_chats":
        await query.answer()
        user = await get_user(uid)
        username = user["username"] if user else (query.from_user.first_name or "Игрок")
        text = (
            f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
            "💭 Официальная беседа бота:\n @bfgbunker_chat\n"
            "💭 Официальный канал новостей бота:\n@bfgbunker\n\n"
            "🚀 Так же ты можешь добавить нашего бота в свой чат, и играть вместе 👫\n"
            "*не забудь дать права администратора*"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить бота в группу", url="https://t.me/bfgbunker_bot?startgroup")],
            [InlineKeyboardButton("◀️ Назад", callback_data="help_back")],
        ])
        await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data.startswith("fuel_full_") or data.startswith("fuel_hour_"):
        uid2 = int(data.split("_")[2])
        if uid2 != uid:
            await query.answer("Это не твой бункер!", show_alert=True)
            return
        await query.answer()
        user2 = await get_user(uid)
        total_income = await get_total_income(uid)
        fuel_per_hour = max(1, total_income // 5)
        max_fuel = fuel_per_hour * 12
        current_fuel = user2.get("fuel", 0)
        if data.startswith("fuel_full_"):
            need = max(0, max_fuel - current_fuel)
        else:
            need = max(0, fuel_per_hour - current_fuel)
        need = int(need)
        if need <= 0:
            await query.answer("Бак уже полный!", show_alert=True)
            return
        if user2["balance"] < need:
            await query.answer(f"Недостаточно крышек! Нужно {fmt_smart(need)} кр.", show_alert=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ?, fuel = fuel + ? WHERE user_id=?",
                             (need, need, uid))
            await db.commit()
        await query.message.edit_text(
            f"⛽️ {user_link(uid, user2['username'])}, ты заправил(-а) бункер на {fmt_smart(need)} л. за {fmt_smart(need)} кр.!",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("room_currency_"):
        parts = data.split("_")
        room_num = int(parts[2])
        currency = parts[3]
        use_bottles = (currency == "bottles")
        context.user_data[f"room_{room_num}_bottles"] = use_bottles
        user = await get_user(uid)
        vip = user.get("vip", 0)
        text = await build_room_text(uid, room_num, use_bottles)
        if text:
            try:
                await query.message.edit_text(text, reply_markup=room_keyboard(room_num, use_bottles, vip=vip), parse_mode=ParseMode.HTML)
            except Exception:
                pass

    elif data.startswith("dig_do_"):
        uid2 = int(data[7:])
        if uid2 != uid:
            await query.answer("Это не твоя шахта!", show_alert=True)
            return
        pending = DIG_PENDING.get(uid)
        if not pending:
            await query.answer("Сначала напиши Копать!", show_alert=True)
            return
        del DIG_PENDING[uid]
        await query.answer()
        res_key = pending["resource"]
        chance = pending["chance"]
        res = MINE_RESOURCES[res_key]
        user2 = await get_user(uid)
        username2 = user2["username"] or "Игрок"
        success = random.randint(1, 100) <= chance
        if success:
            amount = random.randint(1, 3)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    f"UPDATE mine SET {res['col']} = {res['col']} + ?, depth = depth + 1, durability = durability - 1 WHERE user_id=?",
                    (amount, uid)
                )
                await db.commit()
            await query.message.edit_text(
                f"⛏️ {user_link(uid, username2)}, ты успешно выкопал(-а) {res['emoji']} {res['name']} +{amount} кг.!\n"
                f"📉 Глубина: {(await get_mine(uid))['depth']} м.",
                parse_mode=ParseMode.HTML
            )
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE mine SET depth = depth + 1, durability = durability - 1 WHERE user_id=?", (uid,))
                await db.commit()
            await query.message.edit_text(
                f"😓 {user_link(uid, username2)}, не получилось выкопать {res['emoji']} {res['name']}. Не повезло!",
                parse_mode=ParseMode.HTML
            )

    elif data.startswith("dig_skip_"):
        uid2 = int(data[9:])
        if uid2 != uid:
            return
        DIG_PENDING.pop(uid, None)
        await query.answer("Пропущено.")
        await query.message.edit_text("🚬 Ты пропустил(-а) этот ресурс.")

    elif data.startswith("room_up_"):
        parts = data.split("_")
        room_num = int(parts[2])
        levels = int(parts[3])
        use_bottles = (len(parts) >= 5 and parts[4] == "bottles") or context.user_data.get(f"room_{room_num}_bottles", False)

        # Проверка кулдауна на прокачку (раньше этот код был в ветке
        # "room_currency_" и падал с ошибкой, т.к. там нет `levels` —
        # перенесено сюда, где `levels` определена и где кулдаун реально нужен).
        user_cd = await get_user(uid)
        cd_seconds = get_room_upgrade_cd(user_cd.get("vip", 0), levels)
        if cd_seconds > 0:
            cd_key = (uid, room_num, levels)
            last_upgrade = ROOM_UPGRADE_COOLDOWNS.get(cd_key, 0)
            elapsed = time.time() - last_upgrade
            if elapsed < cd_seconds:
                remaining = int(cd_seconds - elapsed) + 1
                mins = remaining // 60
                secs = remaining % 60
                wait_str = f"{mins} мин. {secs} сек." if mins else f"{secs} сек."
                await query.answer(f"⏳ Подождите {wait_str}!", show_alert=True)
                return
            ROOM_UPGRADE_COOLDOWNS[cd_key] = time.time()

        result_data = await do_room_upgrade(uid, room_num, levels, use_bottles)
        if isinstance(result_data, tuple):
            result, fire = result_data
        else:
            result, fire = result_data, False
        if fire:
            fire_user = await get_user(uid)
            fire_name = fire_user["username"] or "Игрок"
            await query.answer(
                f"🔥 {fire_name}, в бункере пожар! Напиши Починить бункер для починки.",
                show_alert=False
            )
        else:
            if result:
                await query.answer(result[:200])
        user = await get_user(uid)
        vip = user.get("vip", 0)
        text = await build_room_text(uid, room_num, use_bottles)
        if text:
            try:
                await query.message.edit_text(text, reply_markup=room_keyboard(room_num, use_bottles, vip=vip), parse_mode=ParseMode.HTML)
            except Exception:
                pass

    elif data.startswith("top_"):
        category = data[4:]
        if not await user_exists(uid):
            await query.answer("Сначала создайте бункер!", show_alert=True)
            return
        user = await get_user(uid)
        text = await build_top_text(uid, category)
        kb = top_keyboard(category)
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    elif data.startswith("ochko_"):
        await query.answer()
        action = data.split("_")[1]  # "hit" или "stop"
        uid2 = int(data.split("_")[2])
        if uid2 != uid:
            await query.answer("Это не твоя игра!", show_alert=True)
            return
        game = OCHKO_GAMES.get(uid)
        if not game:
            await query.message.edit_text("Игра не найдена или уже завершена.")
            return

        username2 = game["username"]
        bet = game["bet"]
        deck = game["deck"]
        player_hand = game["player"]
        dealer_hand = game["dealer"]

        if action == "hit":
            if deck:
                player_hand.append(deck.pop())
            pval = hand_value(player_hand)
            if pval > 21:
                # Перебор
                del OCHKO_GAMES[uid]
                text = (
                    f"♣️ {user_link(uid, username2)}, ты проиграл(-а) ❌\n"
                    f"· · · · · · · · · · · · · · ·\n"
                    f"💸 Ставка: {fmt_smart(bet)} кр.\n"
                    f"🤵‍♂ Дилер:\n"
                    f"{hand_str(dealer_hand)} | {hand_value(dealer_hand)}\n"
                    f"──────────────────\n"
                    f"🫵 Ты:\n"
                    f"{hand_str(player_hand)} | {pval}\n"
                    f"💥 Перебор! У тебя больше 21."
                )
                await query.message.edit_text(text, parse_mode=ParseMode.HTML)
                return
            text = (
                f"♣️ {user_link(uid, username2)}, ты запустил игру 21\n"
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
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            except:
                pass
            OCHKO_GAMES[uid]["player"] = player_hand
            OCHKO_GAMES[uid]["deck"] = deck

        elif action == "stop":
            # Дилер добирает карты до 17
            while hand_value(dealer_hand) < 17 and deck:
                dealer_hand.append(deck.pop())

            pval = hand_value(player_hand)
            dval = hand_value(dealer_hand)
            del OCHKO_GAMES[uid]

            if dval > 21:
                result = "win"
                result_text = "🎉 Ты победил! У дилера перебор."
            elif pval > dval:
                result = "win"
                result_text = "🎉 Ты победил! У тебя больше очков."
            elif pval == dval:
                result = "draw"
                result_text = "🤝 Ничья!"
            else:
                result = "lose"
                result_text = "💥 Ты проиграл(-а)! У дилера больше очков."

            async with aiosqlite.connect(DB_PATH) as db:
                if result == "win":
                    winnings = bet * 2
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (winnings, uid))
                    win_line = f"📊 Выигрыш: +{fmt_smart(bet)} кр.\n"
                    header = f"♣️ {user_link(uid, username2)}, ты выиграл(-а) ✅"
                elif result == "draw":
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (bet, uid))
                    win_line = f"📊 Ничья, ставка возвращена"
                    header = f"♣️ {user_link(uid, username2)}, ничья 🤝"
                else:
                    win_line = f""
                    header = f"♣️ {user_link(uid, username2)}, ты проиграл(-а) ❌"
                await db.commit()

            text = (
                f"{header}\n"
                f"· · · · · · · · · · · · · · ·\n"
                f"💸 Ставка: {fmt_smart(bet)} кр.\n"
                f"{win_line}\n"
                f"🤵‍♂ Дилер:\n"
                f"{hand_str(dealer_hand)} | {dval}\n"
                f"──────────────────\n"
                f"🫵 Ты:\n"
                f"{hand_str(player_hand)} | {pval}\n"
                f"{result_text}"
            )
            await query.message.edit_text(text, parse_mode=ParseMode.HTML)

    elif data.startswith("gh_grow_"):
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
        await ensure_greenhouse(uid)
        gh = await get_greenhouse(uid)
        selected = gh.get("selected_crop") or "картошка"
        await handle_grow(update, user2, ["вырастить", selected, str(qty)])

    elif data.startswith("gh_select_"):
        await query.answer()
        uid2 = int(data.split("_")[2])
        if uid2 != uid:
            return
        user2 = await get_user(uid)
        await ensure_greenhouse(uid)
        gh = await get_greenhouse(uid)
        exp = gh["exp"]
        available = get_available_crops(exp)

        all_crops = list(CROPS.items())
        buttons = []
        row = []
        for i, (name, data_c) in enumerate(all_crops):
            if name in available:
                row.append(InlineKeyboardButton(f"{data_c['emoji']} {name.capitalize()}", callback_data=f"gh_crop_{uid}_{name}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"gh_back_{uid}")])
        kb = InlineKeyboardMarkup(buttons)
        await query.message.edit_text("🪴 Выбери сорт для выращивания:", reply_markup=kb)

    elif data.startswith("gh_crop_"):
        parts = data.split("_")
        uid2 = int(parts[2])
        crop_name = "_".join(parts[3:])
        if uid2 != uid:
            return
        await ensure_greenhouse(uid)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE greenhouse SET selected_crop = ? WHERE user_id=?", (crop_name, uid))
            await db.commit()
        await query.answer(f"Выбрано: {crop_name.capitalize()}")
        # Вернуть к теплице
        user2 = await get_user(uid)
        vip = user2.get("vip", 0)
        gh = await get_greenhouse(uid)
        exp = gh["exp"]
        water = gh["water"]
        water_limit = get_vip_water_limit(vip)
        stock_lines = []
        for crop, cdata in CROPS.items():
            amount = gh.get(cdata["col"], 0)
            if amount > 0:
                stock_lines.append(f"   {cdata['emoji']} {crop.capitalize()} — {amount} шт.")
        stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"
        crop_emoji = CROPS[crop_name]["emoji"]
        text = (
            f"🙎‍♂️ {user_link(uid, user2['username'])}, информация о твоей теплице:\n"
            f"  ⭐️ Опыт: {fmt_smart(exp)}\n"
            f"  💧 Вода: {water}/{water_limit} л.\n"
            f"  🪴 Тебе доступна: {crop_name}\n\n"
            f"📦 Твой склад:\n{stock_text}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔀 Выбрать сорт", callback_data=f"gh_select_{uid}")],
            [InlineKeyboardButton(f"💧 Вырастить {crop_emoji}", callback_data=f"gh_grow_{uid}_1")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except:
            pass

    elif data.startswith("ho_join_"):
        game_id = data[8:]
        game = HO_GAMES.get(game_id)
        if not game:
            await query.answer("Игра не найдена!", show_alert=True)
            return
        if game["active"]:
            await query.answer("Игра уже началась!", show_alert=True)
            return
        if uid == game["p1"]:
            await query.answer("Ты создал эту игру!", show_alert=True)
            return
        p2_user = await get_user(uid)
        if not p2_user or p2_user["balance"] < game["bet"]:
            await query.answer("У тебя недостаточно крышек!", show_alert=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (game["bet"], uid))
            await db.commit()
        game["p2"] = uid
        game["p2_name"] = p2_user["username"] or query.from_user.first_name or "Игрок"
        game["active"] = True
        await query.answer()
        text = ho_board_text(game["board"], game["bet"], game["p1_name"], game["p2_name"])
        text += f"\n\n➡️ Ход: ❌ {game['p1_name']}"
        kb = ho_keyboard(game_id, game["board"])
        await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data.startswith("ho_cancel_"):
        game_id = data[10:]
        game = HO_GAMES.get(game_id)
        if not game:
            await query.answer("Игра не найдена!", show_alert=True)
            return
        if uid != game["p1"]:
            await query.answer("Только создатель может отменить!", show_alert=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (game["bet"], game["p1"]))
            await db.commit()
        del HO_GAMES[game_id]
        await query.answer("Игра отменена, ставка возвращена.")
        await query.message.edit_text("❌ Игра отменена.")

    elif data.startswith("ho_no_"):
        await query.answer("Эта клетка занята!", show_alert=True)

    elif data.startswith("ho_move_"):
        parts = data.split("_")
        game_id = parts[2]
        cell = int(parts[3])
        game = HO_GAMES.get(game_id)
        if not game or not game["active"]:
            await query.answer("Игра не найдена!", show_alert=True)
            return
        # Проверяем чей ход
        if game["turn"] == 1 and uid != game["p1"]:
            await query.answer("Сейчас ход ❌!", show_alert=True)
            return
        if game["turn"] == 2 and uid != game["p2"]:
            await query.answer("Сейчас ход ⭕️!", show_alert=True)
            return
        if game["board"][cell] != 0:
            await query.answer("Клетка занята!", show_alert=True)
            return
        game["board"][cell] = game["turn"]
        winner = ho_check_winner(game["board"])
        if winner == 0:
            game["turn"] = 2 if game["turn"] == 1 else 1
            turn_name = game["p1_name"] if game["turn"] == 1 else game["p2_name"]
            turn_sym = "❌" if game["turn"] == 1 else "⭕️"
            text = ho_board_text(game["board"], game["bet"], game["p1_name"], game["p2_name"])
            text += f"\n\n➡️ Ход: {turn_sym} {turn_name}"
            kb = ho_keyboard(game_id, game["board"])
            await query.answer()
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            except:
                pass
        else:
            prize = game["bet"] * 2
            del HO_GAMES[game_id]
            await query.answer()
            if winner == -1:
                # Ничья — возвращаем ставки
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (game["bet"], game["p1"]))
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (game["bet"], game["p2"]))
                    await db.commit()
                text = ho_board_text(game["board"], game["bet"], game["p1_name"], game["p2_name"])
                text += "\n\n🤝 Ничья! Ставки возвращены."
            else:
                winner_id = game["p1"] if winner == 1 else game["p2"]
                winner_name = game["p1_name"] if winner == 1 else game["p2_name"]
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (prize, winner_id))
                    await db.commit()
                sym = "❌" if winner == 1 else "⭕️"
                text = ho_board_text(game["board"], game["bet"], game["p1_name"], game["p2_name"])
                text += f"\n\n🏆 Победил {sym} {winner_name}!\n💰 Выигрыш: {fmt_smart(prize)} кр."
            try:
                await query.message.edit_text(text, parse_mode=ParseMode.HTML)
            except:
                pass

    elif data.startswith("gh_back_"):
        uid2 = int(data.split("_")[2])
        if uid2 != uid:
            return
        user2 = await get_user(uid)
        vip = user2.get("vip", 0)
        await ensure_greenhouse(uid)
        gh = await get_greenhouse(uid)
        exp = gh["exp"]
        water = gh["water"]
        water_limit = get_vip_water_limit(vip)
        selected = gh.get("selected_crop", "картошка")
        stock_lines = []
        for crop, cdata in CROPS.items():
            amount = gh.get(cdata["col"], 0)
            if amount > 0:
                stock_lines.append(f"   {cdata['emoji']} {crop.capitalize()} — {amount} шт.")
        stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"
        crop_emoji = CROPS.get(selected, CROPS["картошка"])["emoji"]
        text = (
            f"🙎‍♂️ {user_link(uid, user2['username'])}, информация о твоей теплице:\n"
            f"  ⭐️ Опыт: {fmt_smart(exp)}\n"
            f"  💧 Вода: {water}/{water_limit} л.\n"
            f"  🪴 Тебе доступна: {selected}\n\n"
            f"📦 Твой склад:\n{stock_text}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔀 Выбрать сорт", callback_data=f"gh_select_{uid}")],
            [InlineKeyboardButton(f"💧 Вырастить {crop_emoji}", callback_data=f"gh_grow_{uid}_1")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except:
            pass

async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("me", cmd_bunker))
    app.add_handler(CommandHandler("rooms", cmd_rooms_command))
    app.add_handler(CommandHandler("balance", cmd_balance_slash))
    app.add_handler(CommandHandler("ref", cmd_ref_slash))
    app.add_handler(CommandHandler("bonus", cmd_bonus_slash))
    app.add_handler(CommandHandler("donation", cmd_donation_slash))
    app.add_handler(CommandHandler("top", cmd_top_slash))
    app.add_handler(CommandHandler("cases", cmd_cases_slash))
    app.add_handler(CommandHandler("rating", cmd_rating_slash))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    job_queue = app.job_queue
    job_queue.run_repeating(queue_refill_job, interval=1800, first=60)
    job_queue.run_repeating(passive_income_job, interval=1800, first=120)
    job_queue.run_repeating(water_refill_job, interval=600, first=30)
    job_queue.run_repeating(fuel_consume_job, interval=1800, first=90)

    async with app:
        await app.start()
        await app.updater.start_polling()
        print("Бот запущен...")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            if app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
