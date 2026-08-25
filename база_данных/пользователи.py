"""Операции с профилем игрока."""

from datetime import datetime
import aiosqlite

from настройки import DB_PATH


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None


async def create_bunker(user_id: int, username: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)",
            (user_id, username or "Игрок", datetime.now().strftime("%d.%m.%Y")),
        )
        for room_num in (1, 2, 3, 4):
            await db.execute(
                "INSERT INTO rooms (user_id, room_num, level) VALUES (?, ?, 1)",
                (user_id, room_num),
            )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip((item[0] for item in cur.description), row)) if row else None


async def update_balance(user_id: int, change: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (change, user_id))
        await db.commit()
