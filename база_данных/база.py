# -*- coding: utf-8 -*-
import aiosqlite
from datetime import datetime
from настройки import DB_PATH
from вспомогательные.вспомогательные_функции import get_current_income


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 500,
                bottles REAL DEFAULT 0,
                bb_coins INTEGER DEFAULT 0,
                people INTEGER DEFAULT 6,
                queue INTEGER DEFAULT 0,
                registered_at TEXT,
                last_queue_time TEXT DEFAULT NULL,
                rating INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                last_bonus TEXT DEFAULT NULL,
                last_bonus2 TEXT DEFAULT NULL,
                wasteland_hours REAL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                room_num INTEGER,
                level INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS room_extras (
                user_id INTEGER,
                room_num INTEGER,
                med_stock INTEGER DEFAULT 0,
                weapon_stock INTEGER DEFAULT 0,
                matter INTEGER DEFAULT 0,
                diamond INTEGER DEFAULT 0,
                uranium INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, room_num)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_promos (
                user_id INTEGER,
                promo TEXT,
                PRIMARY KEY(user_id, promo)
            )
        """)
       
        for col, col_type, default in [
            ("rating", "INTEGER", "0"),
            ("vip", "INTEGER", "0"),
            ("last_bonus", "TEXT", "NULL"),
            ("last_bonus2", "TEXT", "NULL"),
            ("wasteland_hours", "REAL", "0"),
            ("fuel", "REAL", "0"),
            ("custom_status", "TEXT", "NULL"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type} DEFAULT {default}")
            except:
                pass

# Таблица для пассивного дохода (каждые 30 мин)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS income_log (
                user_id INTEGER PRIMARY KEY,
                last_income_time TEXT DEFAULT NULL
            )
        """)

        # Бочки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS barrels (
                user_id INTEGER PRIMARY KEY,
                barrel_1 INTEGER DEFAULT 0,
                barrel_2 INTEGER DEFAULT 0,
                barrel_3 INTEGER DEFAULT 0
            )
        """)

        # Теплица
        await db.execute("""
            CREATE TABLE IF NOT EXISTS greenhouse (
                user_id INTEGER PRIMARY KEY,
                exp INTEGER DEFAULT 0,
                water INTEGER DEFAULT 0,
                last_water_refill TEXT DEFAULT NULL,
                selected_crop TEXT DEFAULT 'картошка',
                potato INTEGER DEFAULT 0,
                carrot INTEGER DEFAULT 0,
                rice INTEGER DEFAULT 0,
                garlic INTEGER DEFAULT 0,
                beet INTEGER DEFAULT 0,
                cucumber INTEGER DEFAULT 0,
                cabbage INTEGER DEFAULT 0,
                beans INTEGER DEFAULT 0,
                tomato INTEGER DEFAULT 0,
                eggplant INTEGER DEFAULT 0
            )
        """)

        # Шахта
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mine (
                user_id INTEGER PRIMARY KEY,
                pickaxe INTEGER DEFAULT 0,
                durability INTEGER DEFAULT 0,
                depth INTEGER DEFAULT 0,
                sand INTEGER DEFAULT 0,
                coal INTEGER DEFAULT 0,
                iron INTEGER DEFAULT 0,
                copper INTEGER DEFAULT 0,
                silver INTEGER DEFAULT 0,
                diamond INTEGER DEFAULT 0,
                uranium INTEGER DEFAULT 0
            )
        """)

        # Починка бункера
        try:
            await db.execute("ALTER TABLE users ADD COLUMN bunker_broken INTEGER DEFAULT 0")
        except:
            pass

        await db.commit()

async def create_bunker(user_id: int, username: str):
    now = datetime.now().strftime("%d.%m.%Y")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, registered_at) VALUES (?, ?, ?)",
            (user_id, username or "Игрок", now)
        )
        for rn in [1, 2, 3, 4]:
            await db.execute(
                "INSERT INTO rooms (user_id, room_num, level) VALUES (?, ?, 1)",
                (user_id, rn)
            )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def get_rooms(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT room_num, level FROM rooms WHERE user_id = ? ORDER BY room_num", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [{"room_num": r[0], "level": r[1]} for r in rows]

async def get_room_extra(user_id: int, room_num: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM room_extras WHERE user_id=? AND room_num=?", (user_id, room_num)
        ) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def get_room_level(user_id: int, room_num: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT level FROM rooms WHERE user_id=? AND room_num=?", (user_id, room_num)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def get_total_income(user_id: int) -> int:
    rooms = await get_rooms(user_id)
    return sum(get_current_income(r["room_num"], r["level"]) for r in rooms)
