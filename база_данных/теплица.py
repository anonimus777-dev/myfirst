"""Доступ к данным теплицы."""

import aiosqlite

from настройки import DB_PATH

CROPS = {
    "картошка": {"emoji": "🥔", "exp_req": 0, "sell_price": 100, "col": "potato"},
    "морковь": {"emoji": "🥕", "exp_req": 500, "sell_price": 200, "col": "carrot"},
    "рис": {"emoji": "🍚", "exp_req": 2000, "sell_price": 600, "col": "rice"},
    "чеснок": {"emoji": "🧄", "exp_req": 5000, "sell_price": 1000, "col": "garlic"},
    "свекла": {"emoji": "🍠", "exp_req": 10000, "sell_price": 1400, "col": "beet"},
    "огурец": {"emoji": "🥒", "exp_req": 25000, "sell_price": 2500, "col": "cucumber"},
    "капуста": {"emoji": "🥬", "exp_req": 40000, "sell_price": 3500, "col": "cabbage"},
    "фасоль": {"emoji": "🫘", "exp_req": 60000, "sell_price": 5000, "col": "beans"},
    "помидор": {"emoji": "🍅", "exp_req": 100000, "sell_price": 10000, "col": "tomato"},
    "баклажан": {"emoji": "🍆", "exp_req": 125000, "sell_price": 20000, "col": "eggplant"},
}


async def get_greenhouse(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM greenhouse WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip((col[0] for col in cur.description), row)) if row else None


async def ensure_greenhouse(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO greenhouse (user_id) VALUES (?)", (user_id,))
        await db.commit()


def get_available_crops(exp: int) -> list[str]:
    return [name for name, data in CROPS.items() if data["exp_req"] <= exp]
