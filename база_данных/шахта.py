"""Данные шахты и игровые справочники."""

import aiosqlite

from настройки import DB_PATH

PICKAXES = {
    1: {"name": "Каменная кирка", "price": 30000, "durability": 1, "emoji": "⛏️"},
    2: {"name": "Железная кирка", "price": 200000, "durability": 3, "emoji": "⛏️"},
    3: {"name": "Алмазная кирка", "price": 1000000, "durability": 5, "emoji": "💎"},
}
MINE_RESOURCES = {
    "sand": {"emoji": "🏜️", "name": "Песок", "sell": 2000},
    "coal": {"emoji": "◾️", "name": "Уголь", "sell": 5000},
    "iron": {"emoji": "🚂", "name": "Железо", "sell": 8000},
    "copper": {"emoji": "🟠", "name": "Медь", "sell": 12000},
    "silver": {"emoji": "🥈", "name": "Серебро", "sell": 18000},
    "diamond": {"emoji": "💎", "name": "Алмаз", "sell": 60000},
    "uranium": {"emoji": "☢️", "name": "Уран", "sell": 150000},
}
MINE_CHANCES = {
    "sand": [100, 100, 100], "coal": [85, 100, 100], "iron": [50, 90, 100],
    "copper": [30, 50, 80], "silver": [0, 40, 70], "diamond": [0, 30, 60],
    "uranium": [0, 10, 40],
}


async def get_mine(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM mine WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip((col[0] for col in cur.description), row)) if row else None


async def ensure_mine(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO mine (user_id) VALUES (?)", (user_id,))
        await db.commit()


def get_mine_chances_by_depth(depth: int, pickaxe_idx: int) -> dict[str, int]:
    unlocked = 1 + depth // 10
    chances = {}
    for index, resource in enumerate(MINE_RESOURCES):
        chances[resource] = MINE_CHANCES[resource][pickaxe_idx - 1] if index < unlocked else 0
    return chances
