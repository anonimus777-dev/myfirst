"""Тексты сообщений и описаний разделов бота."""
# -*- coding: utf-8 -*-
import aiosqlite
from настройки import DB_PATH, ROOMS_DATA, ROOM_BUY_PRICES, NUM_EMOJIS
from вспомогательные.вспомогательные_функции import (
    fmt_smart, fmt_bottles, user_link, safe_nick, get_current_income,
    get_upgrade_cost, get_balance_limit, get_vip_level_name,
)
from база_данных.база import get_user, get_rooms, get_room_level, get_total_income, get_room_extra


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

    # Максимальная вместимость бункера определяется самой маленькой
    # вместимостью среди всех купленных комнат.
    room_capacities = [
        ROOMS_DATA[r["room_num"]]["capacity"] + (r["level"] - 1) * 2
        for r in rooms
    ]
    max_people = min(room_capacities) if room_capacities else 0

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
        f"  Макс. вместимость людей: {max_people}\n\n"
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
def ho_board_text(board: list, bet: int, p1_name: str, p2_name: str) -> str:
    symbols = {0: "⬜", 1: "❌", 2: "⭕️"}
    rows = []
    for i in range(3):
        rows.append(" ".join(symbols[board[i*3+j]] for j in range(3)))
    return (
        f"❌⭕️ Крестики-нолики\n"
        f"💸 Ставка: {fmt_smart(bet)} кр.\n\n"
        + "\n".join(rows) +
        f"\n\n❌ {p1_name}\n⭕️ {p2_name}"
    )
