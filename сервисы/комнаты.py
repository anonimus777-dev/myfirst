"""Расчёты и транзакции для комнат бункера."""

import random
import aiosqlite

from настройки import DB_PATH

ROOMS_DATA = {
    1: ("Теплица", 80, 1, 2.5, 0), 2: ("Генераторная", 80, 1, 2.5, 0),
    3: ("Столовая", 80, 1, 2.5, 0), 4: ("Станция обработки воды", 80, 1, 2.5, 0),
    5: ("Сейф", 151, 1, 3.0, 5), 6: ("Игровая комната", 202, 2, 3.0, 12),
    7: ("Медпункт", 300, 3, 3.0, 24), 8: ("Радиостанция", 505, 5, 3.0, 40),
    9: ("Оружейная", 808, 8, 3.0, 80), 10: ("Кухня", 1515, 15, 3.0, 130),
    11: ("Гостиная", 2323, 23, 3.0, 220), 12: ("Шахта", 3434, 34, 3.0, 360),
    13: ("Лаборатория", 5000, 50, 3.0, 500), 14: ("Сад", 7570, 70, 3.0, 720),
    15: ("Автомастерская", 10100, 100, 3.0, 1000), 16: ("Гильдия", 18180, 180, 3.0, 1400),
    17: ("Киберспортивная", 30300, 300, 3.0, 2000), 18: ("Адронный коллайдер", 101000, 1000, 3.0, 3500),
    19: ("Реактор", 202000, 2000, 3.0, 5000),
}
ROOM_BUY_PRICES = {room_num: 150 * 2 ** (room_num - 5) for room_num in range(5, 20)}


def room_name(room_num: int) -> str:
    return ROOMS_DATA[room_num][0]


def get_current_income(room_num: int, level: int) -> int:
    _, base, increment, _, _ = ROOMS_DATA[room_num]
    return base + increment * (level - 1)


def get_upgrade_cost(room_num: int, current_level: int) -> int:
    return int(get_current_income(room_num, current_level) * ROOMS_DATA[room_num][3])


def get_balance_limit(rooms: list[dict]) -> int:
    return 10_000 + sum(room["level"] * 1000 for room in rooms if room["room_num"] == 5)


async def buy_room(user_id: int, room_num: int) -> tuple[bool, str]:
    if room_num not in ROOM_BUY_PRICES:
        return False, "Можно купить комнаты с 5 по 19."
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, people FROM users WHERE user_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()
        async with db.execute("SELECT 1 FROM rooms WHERE user_id = ? AND room_num = ?", (user_id, room_num)) as cur:
            if await cur.fetchone():
                return False, "Эта комната уже куплена."
        price = ROOM_BUY_PRICES[room_num]
        if user[1] < ROOMS_DATA[room_num][4]:
            return False, "Недостаточно людей в бункере."
        if user[0] < price:
            return False, "Недостаточно крышек."
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
        await db.execute("INSERT INTO rooms (user_id, room_num, level) VALUES (?, ?, 1)", (user_id, room_num))
        await db.commit()
    return True, room_name(room_num)


async def upgrade_room(user_id: int, room_num: int, levels: int, use_bottles: bool) -> tuple[bool, int, bool]:
    if levels not in (1, 5, 20, 100, 1000, 5000):
        return False, 0, False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, bottles, vip FROM users WHERE user_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()
        async with db.execute("SELECT level FROM rooms WHERE user_id = ? AND room_num = ?", (user_id, room_num)) as cur:
            room = await cur.fetchone()
        if not user or not room:
            return False, 0, False
        required_vip = {20: 1, 100: 2, 1000: 3, 5000: 4}.get(levels, 0)
        if user[2] < required_vip:
            return False, 0, False
        cost = sum(get_upgrade_cost(room_num, room[0] + step) for step in range(levels))
        if use_bottles:
            spent = cost / 10_000
            if user[1] < spent:
                return False, cost, False
            await db.execute("UPDATE users SET bottles = bottles - ? WHERE user_id = ?", (spent, user_id))
        else:
            if user[0] < cost:
                return False, cost, False
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (cost, user_id))
        await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?", (levels, user_id, room_num))
        broken = random.randint(1, 100) <= {1: 1, 5: 3, 20: 10, 100: 15, 1000: 25, 5000: 25}[levels]
        if broken:
            await db.execute("UPDATE users SET bunker_broken = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
    return True, cost, broken
