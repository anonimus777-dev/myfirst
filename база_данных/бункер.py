"""Данные бункера: комнаты, бочки и состояние ремонта."""

import aiosqlite

from настройки import DB_PATH

BARREL_PRICES = {1: 5_000, 2: 30_000, 3: 30}
BARREL_COLUMNS = {1: "barrel_1", 2: "barrel_2", 3: "barrel_3"}


async def get_barrels(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM barrels WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return dict(zip((column[0] for column in cur.description), row))
    return {"user_id": user_id, "barrel_1": 0, "barrel_2": 0, "barrel_3": 0}


async def ensure_barrels(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO barrels (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def add_barrels(user_id: int, barrel_num: int, quantity: int) -> None:
    column = BARREL_COLUMNS[barrel_num]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE barrels SET {column} = {column} + ? WHERE user_id = ?", (quantity, user_id))
        await db.commit()


async def remove_barrels(user_id: int, barrel_num: int, quantity: int) -> None:
    column = BARREL_COLUMNS[barrel_num]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE barrels SET {column} = {column} - ? WHERE user_id = ?", (quantity, user_id))
        await db.commit()


async def set_bunker_broken(user_id: int, broken: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET bunker_broken = ? WHERE user_id = ?", (int(broken), user_id))
        await db.commit()
