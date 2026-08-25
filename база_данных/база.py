"""Инициализация SQLite и операции с профилем игрока."""

from datetime import datetime
import aiosqlite

from настройки import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 500,
                bottles REAL DEFAULT 0, bb_coins INTEGER DEFAULT 0,
                people INTEGER DEFAULT 6, queue INTEGER DEFAULT 0,
                registered_at TEXT, last_queue_time TEXT DEFAULT NULL,
                rating INTEGER DEFAULT 0, vip INTEGER DEFAULT 0,
                last_bonus TEXT DEFAULT NULL, last_bonus2 TEXT DEFAULT NULL,
                wasteland_hours REAL DEFAULT 0, fuel REAL DEFAULT 0,
                custom_status TEXT DEFAULT NULL, bunker_broken INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                room_num INTEGER, level INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS room_extras (
                user_id INTEGER, room_num INTEGER, med_stock INTEGER DEFAULT 0,
                weapon_stock INTEGER DEFAULT 0, matter INTEGER DEFAULT 0,
                diamond INTEGER DEFAULT 0, uranium INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, room_num)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_promos (
                user_id INTEGER, promo TEXT, PRIMARY KEY(user_id, promo)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS income_log (
                user_id INTEGER PRIMARY KEY, last_income_time TEXT DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS barrels (
                user_id INTEGER PRIMARY KEY, barrel_1 INTEGER DEFAULT 0,
                barrel_2 INTEGER DEFAULT 0, barrel_3 INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS greenhouse (
                user_id INTEGER PRIMARY KEY, exp INTEGER DEFAULT 0,
                water INTEGER DEFAULT 0, last_water_refill TEXT DEFAULT NULL,
                selected_crop TEXT DEFAULT 'картошка', potato INTEGER DEFAULT 0,
                carrot INTEGER DEFAULT 0, rice INTEGER DEFAULT 0, garlic INTEGER DEFAULT 0,
                beet INTEGER DEFAULT 0, cucumber INTEGER DEFAULT 0, cabbage INTEGER DEFAULT 0,
                beans INTEGER DEFAULT 0, tomato INTEGER DEFAULT 0, eggplant INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mine (
                user_id INTEGER PRIMARY KEY, pickaxe INTEGER DEFAULT 0,
                durability INTEGER DEFAULT 0, depth INTEGER DEFAULT 0,
                sand INTEGER DEFAULT 0, coal INTEGER DEFAULT 0, iron INTEGER DEFAULT 0,
                copper INTEGER DEFAULT 0, silver INTEGER DEFAULT 0, diamond INTEGER DEFAULT 0,
                uranium INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None


async def create_bunker(user_id: int, username: str) -> None:
    now = datetime.now().strftime("%d.%m.%Y")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)",
            (user_id, username or "Игрок", now),
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
            return dict(zip((col[0] for col in cur.description), row)) if row else None


async def get_rooms(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT room_num, level FROM rooms WHERE user_id = ? ORDER BY room_num",
            (user_id,),
        ) as cur:
            return [{"room_num": row[0], "level": row[1]} for row in await cur.fetchall()]


async def get_room_extra(user_id: int, room_num: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM room_extras WHERE user_id = ? AND room_num = ?",
            (user_id, room_num),
        ) as cur:
            row = await cur.fetchone()
            return dict(zip((col[0] for col in cur.description), row)) if row else None


async def has_room(user_id: int, room_num: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM rooms WHERE user_id = ? AND room_num = ?",
            (user_id, room_num),
        ) as cur:
            return await cur.fetchone() is not None


async def get_room_level(user_id: int, room_num: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT level FROM rooms WHERE user_id = ? AND room_num = ?",
            (user_id, room_num),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0
