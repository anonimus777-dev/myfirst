import asyncio
import os
from email.mime import text
from turtle import update
from unicodedata import category
from unicodedata import category
import aiosqlite
import random
from datetime import datetime, timedelta, date, time as dtime
import datetime as dt_module
from datetime import datetime, timedelta, date
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
import html

def safe_nick(name: str) -> str:
    return html.escape(name)


BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана.")
OCHKO_GAMES = {} 
HO_GAMES = {}
ADMIN_IDS = {6112843760}
DB_PATH = "bunker.db"
GAME_COOLDOWNS = {}
ROOM_UPGRADE_COOLDOWNS = {}

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

ROOMS_DATA = {
    1:  {"name": "Теплица",               "income": 80,      "inc_per_lvl": 1,    "capacity": 6,    "upgrade_cost": 200,     "coef": 2.5, "unlock_people": 0},
    2:  {"name": "Генераторная",           "income": 80,      "inc_per_lvl": 1,    "capacity": 6,    "upgrade_cost": 200,     "coef": 2.5, "unlock_people": 0},
    3:  {"name": "Столовая",               "income": 80,      "inc_per_lvl": 1,    "capacity": 6,    "upgrade_cost": 200,     "coef": 2.5, "unlock_people": 0},
    4:  {"name": "Станция обработки воды", "income": 80,      "inc_per_lvl": 1,    "capacity": 6,    "upgrade_cost": 200,     "coef": 2.5, "unlock_people": 0},
    5:  {"name": "Сейф",                   "income": 151,     "inc_per_lvl": 1,    "capacity": 12,   "upgrade_cost": 453,     "coef": 3.0, "unlock_people": 5},
    6:  {"name": "Игровая комната",        "income": 202,     "inc_per_lvl": 2,    "capacity": 20,   "upgrade_cost": 606,     "coef": 3.0, "unlock_people": 12},
    7:  {"name": "Медпункт",               "income": 300,     "inc_per_lvl": 3,    "capacity": 32,   "upgrade_cost": 900,     "coef": 3.0, "unlock_people": 24},
    8:  {"name": "Радиостанция",           "income": 505,     "inc_per_lvl": 5,    "capacity": 52,   "upgrade_cost": 1515,    "coef": 3.0, "unlock_people": 40},
    9:  {"name": "Оружейная",              "income": 808,     "inc_per_lvl": 8,    "capacity": 92,   "upgrade_cost": 2424,    "coef": 3.0, "unlock_people": 80},
    10: {"name": "Кухня",                  "income": 1515,    "inc_per_lvl": 15,   "capacity": 144,  "upgrade_cost": 4545,    "coef": 3.0, "unlock_people": 130},
    11: {"name": "Гостиная",               "income": 2323,    "inc_per_lvl": 23,   "capacity": 234,  "upgrade_cost": 6969,    "coef": 3.0, "unlock_people": 220},
    12: {"name": "Шахта",                  "income": 3434,    "inc_per_lvl": 34,   "capacity": 380,  "upgrade_cost": 10302,   "coef": 3.0, "unlock_people": 360},
    13: {"name": "Лаборатория",            "income": 5000,    "inc_per_lvl": 50,   "capacity": 520,  "upgrade_cost": 15000,   "coef": 3.0, "unlock_people": 500},
    14: {"name": "Сад",                    "income": 7570,    "inc_per_lvl": 70,   "capacity": 750,  "upgrade_cost": 22710,   "coef": 3.0, "unlock_people": 720},
    15: {"name": "Автомастерская",         "income": 10100,   "inc_per_lvl": 100,  "capacity": 1030, "upgrade_cost": 30300,   "coef": 3.0, "unlock_people": 1000},
    16: {"name": "Гильдия",               "income": 18180,   "inc_per_lvl": 180,  "capacity": 1430, "upgrade_cost": 54540,   "coef": 3.0, "unlock_people": 1400},
    17: {"name": "Киберспортивная",        "income": 30300,   "inc_per_lvl": 300,  "capacity": 2020, "upgrade_cost": 90900,   "coef": 3.0, "unlock_people": 2000},
    18: {"name": "Адронный коллайдер",     "income": 101000,  "inc_per_lvl": 1000, "capacity": 3520, "upgrade_cost": 303000,  "coef": 3.0, "unlock_people": 3500},
    19: {"name": "Реактор",               "income": 202000,  "inc_per_lvl": 2000, "capacity": 5020, "upgrade_cost": 606000,  "coef": 3.0, "unlock_people": 5000},
}

ROOM_BUY_PRICES = {}
price = 150
for i in range(5, 20):
    ROOM_BUY_PRICES[i] = price
    price *= 2

NUM_EMOJIS = {
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
    6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
    11: "1️⃣1️⃣", 12: "1️⃣2️⃣", 13: "1️⃣3️⃣", 14: "1️⃣4️⃣", 15: "1️⃣5️⃣",
    16: "1️⃣6️⃣", 17: "1️⃣7️⃣", 18: "1️⃣8️⃣", 19: "1️⃣9️⃣",
}

RP_COMMANDS = {
    "изнасиловать": ("изнасиловал(-а)", "насилует"),
    "выебать": ("выебал(-а)", "выебал(-а)"),
    "испугать": ("испугал(-а)", "пугает"),
    "кусь": ("укусил(-а)", "кусает"),
    "кастрировать": ("кастрировал(-а)", "кастрирует"),
    "лизнуть": ("лизнул(-а)", "лижет"),
    "обнять": ("обнял(-а)", "обнимает"),
    "поцеловать": ("поцеловал(-а)", "целует"),
    "поздравить": ("поздравил(-а)", "поздравляет"),
    "прижать": ("прижал(-а)", "прижимает"),
    "потрогать": ("потрогал(-а)", "трогает"),
    "пожать руку": ("пожал(-а) руку", "жмёт руку"),
    "послать нахуй": ("послал(-а) нахуй", "посылает нахуй"),
    "похвалить": ("похвалил(-а)", "хвалит"),
    "понюхать": ("понюхал(-а)", "нюхает"),
    "погладить": ("погладил(-а)", "гладит"),
    "дать по лбу": ("дал(-а) по лбу", "даёт по лбу"),
    "пнуть": ("пнул(-а)", "пинает"),
    "покормить": ("покормил(-а)", "кормит"),
    "расстрелять": ("расстрелял(-а)", "расстреливает"),
    "трахнуть": ("трахнул(-а)", "трахает"),
    "ударить": ("ударил(-а)", "ударяет"),
    "отдаться": ("отдался(-лась)", "отдаётся"),
    "сделать минет": ("сделал(-а) минет", "делает минет"),
    "сжечь": ("сжёг(сожгла)", "сжигает"),
    "пригласить на чай": ("пригласил(-а) на чай", "приглашает на чай"),
    "связать": ("связал(-а)", "связывает"),
    "похоронить": ("похоронил(-а)", "хоронит"),
    "унизить": ("унизил(-а)", "унижает"),
    "наорать": ("наорал(-а)", "орёт"),
    "наказать": ("наказал(-а)", "наказывает"),
    "сходить в кино": ("сходил(-а) в кино с", "идёт в кино с"),
    "подарить шоколадку": ("подарил(-а) шоколадку", "дарит шоколадку"),
    "кинуть мем": ("кинул(-а) мем", "кидает мем"),
    "поделится едой": ("поделился(-лась) едой с", "делится едой с"),
    "пригласить в клуб": ("пригласил(-а) в клуб", "приглашает в клуб"),
    "поговорить по душам": ("поговорил(-а) по душам с", "говорит по душам с"),
    "рассмешить": ("рассмешил(-а)", "смешит"),
    "сделать засос": ("сделал(-а) засос", "делает засос"),
    "отлизать": ("отлизал(-а)", "отлизывает"),
    "приютить": ("приютил(-а)", "приютил(-а)"),
    "продать": ("продал(-а)", "продаёт"),
    "принять душ": ("принял(-а) душ с", "принимает душ с"),
    "арестовать": ("арестовал(-а)", "арестовывает"),
    "пожелать спокойной ночи": ("пожелал(-а) спокойной ночи", "желает спокойной ночи"),
    "лечь": ("лёг(легла) с", "ложится с"),
    "убить": ("убил(-а)", "убивает"),
    "уебать": ("уебал(-а)", "уёбывает"),
    "облизать": ("облизал(-а)", "облизывает"),
    "раздеть": ("раздел(-а)", "раздевает"),
    "приготовить ужин": ("приготовил(-а) ужин для", "готовит ужин для"),
    "прогуляться": ("прогулялся(-лась) с", "гуляет с"),
    "поработить": ("поработил(-а)", "порабощает"),
    "отпиздохать": ("отпиздохал(-а)", "отпиздохивает"),
}

# Промокоды: promo_code -> {"reward_type": "coins/bottles/rating/bbcoins/exp", "amount": N, "uses_left": N or None}
PROMO_CODES = {
    # Пример: "тест": {"reward_type": "coins", "amount": 1000, "uses_left": None}
}

# Рейтинг цены
RATING_BUY_PRICE = 10000   # крышек за 1 рейтинг
RATING_SELL_PRICE = 8000   # крышек за 1 рейтинг


# ── Crops config ──────────────────────────────────────────────────────────────
CROPS = {
    "картошка":  {"emoji": "🥔", "exp_req": 0,       "sell_price": 100,   "col": "potato"},
    "морковь":   {"emoji": "🥕", "exp_req": 500,     "sell_price": 200,   "col": "carrot"},
    "рис":       {"emoji": "🍚", "exp_req": 2000,    "sell_price": 600,   "col": "rice"},
    "чеснок":    {"emoji": "🧄", "exp_req": 5000,    "sell_price": 1000,  "col": "garlic"},
    "свекла":    {"emoji": "🍠", "exp_req": 10000,   "sell_price": 1400,  "col": "beet"},
    "огурец":    {"emoji": "🥒", "exp_req": 25000,   "sell_price": 2500,  "col": "cucumber"},
    "капуста":   {"emoji": "🥬", "exp_req": 40000,   "sell_price": 3500,  "col": "cabbage"},
    "фасоль":    {"emoji": "🫘", "exp_req": 60000,   "sell_price": 5000,  "col": "beans"},
    "помидор":   {"emoji": "🍅", "exp_req": 100000,  "sell_price": 10000, "col": "tomato"},
    "баклажан":  {"emoji": "🍆", "exp_req": 125000,  "sell_price": 20000, "col": "eggplant"},
}

# ── Mine config ────────────────────────────────────────────────────────────────
PICKAXES = {
    1: {"name": "Каменная кирка",  "price": 30000,    "durability": 1, "emoji": "⛏️"},
    2: {"name": "Железная кирка",  "price": 200000,   "durability": 3, "emoji": "⛏️"},
    3: {"name": "Алмазная кирка",  "price": 1000000,  "durability": 5, "emoji": "💎"},
}

MINE_RESOURCES = {
    "sand":    {"emoji": "🏜️", "name": "Песок",   "sell": 2000,   "col": "sand"},
    "coal":    {"emoji": "◾️", "name": "Уголь",   "sell": 5000,   "col": "coal"},
    "iron":    {"emoji": "🚂", "name": "Железо",  "sell": 8000,   "col": "iron"},
    "copper":  {"emoji": "🟠", "name": "Медь",    "sell": 12000,  "col": "copper"},
    "silver":  {"emoji": "🥈", "name": "Серебро", "sell": 18000,  "col": "silver"},
    "diamond": {"emoji": "💎", "name": "Алмаз",   "sell": 60000,  "col": "diamond"},
    "uranium": {"emoji": "☢️", "name": "Уран",    "sell": 150000, "col": "uranium"},
}

# Шансы по типу кирки [каменная, железная, алмазная]
MINE_CHANCES = {
    "sand":    [100, 100, 100],
    "coal":    [85,  100, 100],
    "iron":    [50,  90,  100],
    "copper":  [30,  50,  80],
    "silver":  [0,   40,  70],
    "diamond": [0,   30,  60],
    "uranium": [0,   10,  40],
}


def get_room_upgrade_cd(vip: int, levels: int) -> int:
    """Возвращает кулдаун в секундах для прокачки комнаты."""
    cd_map = {
        2: {20: 45},
        3: {20: 30, 100: 60},
        4: {20: 20, 100: 45, 1000: 120},
    }
    if vip not in cd_map:
        return 0
    return cd_map[vip].get(levels, 0)

# ── VIP water limits ───────────────────────────────────────────────────────────
def get_vip_water_limit(vip: int) -> int:
    return {0: 20, 1: 30, 2: 50, 3: 75, 4: 100}.get(vip, 20)

def get_vip_barrel_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 25, 4: 50}.get(vip, 1)

def get_vip_grow_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 15, 4: 20}.get(vip, 1)

CARD_DECK = []
for suit in ["♠️", "♥️", "♦️", "♣️"]:
    for val in ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]:
        CARD_DECK.append((val, suit))

def card_value(card):
    v = card[0]
    if v in ["J","Q","K"]:
        return 10
    if v == "A":
        return 11
    return int(v)

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def hand_str(hand):
    return " • ".join(f"{c[0]}{c[1]}" for c in hand)


def fmt_bottles(n: float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}kk"
    return f"{n:,.1f}"

def fmt_smart(n):
    try:
        n = float(n)
    except:
        return str(n)
    abs_n = abs(n)
    if abs_n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.2f}kkkk"
    if abs_n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}kkk"
    if abs_n >= 1_000_000:
        return f"{n/1_000_000:.2f}kk"
    return f"{int(n):,}".replace(",", ",")

fmt = fmt_smart


def fmt_smart(n):
    try:
        n = float(n)
    except:
        return str(n)
    abs_n = abs(n)
    if abs_n >= 1_000_000_000_000:
        return f"{n/1_000_000_000_000:.2f}kkkk"
    if abs_n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}kkk"
    if abs_n >= 1_000_000:
        return f"{n/1_000_000:.2f}kk"
    return f"{int(n):,}".replace(",", ",")

fmt = fmt_smart

def parse_bet(s: str, balance: float) -> int:
    """Парсит ставку: число, 1k, 1kk, всё, all."""
    s = s.lower().strip()
    if s in ("всё", "все", "all"):
        return int(balance)
    try:
        if s.endswith("kkkk"):
            return int(float(s[:-4]) * 1_000_000_000_000)
        if s.endswith("kkk"):
            return int(float(s[:-3]) * 1_000_000_000)
        if s.endswith("kk"):
            return int(float(s[:-2]) * 1_000_000)
        if s.endswith("k"):
            return int(float(s[:-1]) * 1_000)
        return int(s)
    except:
        return -1

def user_link(user_id: int, name: str) -> str:
    """Обернуть имя игрока в кликабельную ссылку"""
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def get_upgrade_cost(room_num: int, current_level: int) -> int:
    coef = ROOMS_DATA[room_num]["coef"]
    current_income = get_current_income(room_num, current_level)
    return int(current_income * coef)


def get_current_income(room_num: int, level: int) -> int:
    base = ROOMS_DATA[room_num]["income"]
    inc = ROOMS_DATA[room_num]["inc_per_lvl"]
    return base + inc * (level - 1)


def get_balance_limit(rooms: list) -> int:
    base = 10000
    for r in rooms:
        if r["room_num"] == 5:
            base += r["level"] * 1000
    return base


def get_vip_transfer_limit(vip: int) -> int:
    limits = {0: 3000, 1: 5000, 2: 8000, 3: 15000, 4: 25000}
    return limits.get(vip, 3000)


def get_vip_level_name(vip: int) -> str:
    names = {0: "Нет", 1: "VIP1 ⚡️", 2: "VIP2 🔥", 3: "VIP3 💎", 4: "VIP4 ⭐️"}
    return names.get(vip, "Нет")


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


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None


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


async def has_room(user_id: int, room_num: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM rooms WHERE user_id=? AND room_num=?", (user_id, room_num)
        ) as cur:
            return await cur.fetchone() is not None


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


def no_bunker_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏗 Создать бункер", callback_data="create_bunker")]])


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="help_back")]])


def help_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Основное", callback_data="help_main"),
         InlineKeyboardButton("🎲 Игры", callback_data="help_games")],
        [InlineKeyboardButton("💥 Активности", callback_data="help_activities"),
         InlineKeyboardButton("💬 Чаты", callback_data="help_chats")],
    ])


def room_keyboard(room_num: int, use_bottles: bool = False, vip: int = 0) -> InlineKeyboardMarkup:
    currency_btn1 = InlineKeyboardButton("За 💰 [✅]" if not use_bottles else "За 💰", callback_data=f"room_currency_{room_num}_coins")
    currency_btn2 = InlineKeyboardButton("За 🍾 [✅]" if use_bottles else "За 🍾", callback_data=f"room_currency_{room_num}_bottles")
    rows = [
        [currency_btn1, currency_btn2],
        [InlineKeyboardButton("🔝 UP +1ур.", callback_data=f"room_up_{room_num}_1"),
         InlineKeyboardButton("🔝 UP +5ур.", callback_data=f"room_up_{room_num}_5")],
        [InlineKeyboardButton("🔝 UP +20ур.", callback_data=f"room_up_{room_num}_20"),
         InlineKeyboardButton("🔝 UP +100ур.", callback_data=f"room_up_{room_num}_100")],
        [InlineKeyboardButton("🔝 UP +1'000ур.", callback_data=f"room_up_{room_num}_1000")],
        [InlineKeyboardButton("🔝 UP +5'000ур.", callback_data=f"room_up_{room_num}_5000")],
    ]
    return InlineKeyboardMarkup(rows)


# TOP keyboards
def top_keyboard(current: str) -> InlineKeyboardMarkup:
    """
    Returns inline keyboard for /top with current category excluded (moved to its position).
    Categories: rating, income, coins, greenhouse, wasteland, guilds, residents, bottles
    Layout when 'rating' is current:
      Row1: 💵 Доход | 💰 Крышки
      Row2: ⭐️ Теплица | 🏜 Пустошь
      Row3: 🏰 Гильдии | 🧍 Жители
      Row4: 🍾 Бутылки
    """
    all_cats = [
        ("rating",    "🏆 Рейтинг"),
        ("income",    "💵 Доход"),
        ("coins",     "💰 Крышки"),
        ("greenhouse","⭐️ Теплица"),
        ("wasteland", "🏜 Пустошь"),
        ("guilds",    "🏰 Гильдии"),
        ("residents", "🧍 Жители"),
        ("bottles",   "🍾 Бутылки"),
    ]
    # Remove current from list, put it first
    others = [c for c in all_cats if c[0] != current]
    # bottles always last row alone
    bottles_cat = next((c for c in others if c[0] == "bottles"), None)
    non_bottles = [c for c in others if c[0] != "bottles"]

    rows = []
    for i in range(0, len(non_bottles), 2):
        row = []
        for cat in non_bottles[i:i+2]:
            row.append(InlineKeyboardButton(cat[1], callback_data=f"top_{cat[0]}"))
        rows.append(row)
    if bottles_cat:
        rows.append([InlineKeyboardButton(bottles_cat[1], callback_data=f"top_{bottles_cat[0]}")])
    return InlineKeyboardMarkup(rows)


async def require_bunker(update: Update) -> bool:
    uid = update.effective_user.id
    if not await user_exists(uid):
        kb = no_bunker_keyboard()
        text = "Сначала создайте Бункер чтобы пользоваться ботом с командой Создать бункер, либо по кнопке ниже"
        if update.message:
            await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return False
    return True


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
        f"  Макс. вместимость людей: {user['people']}\n\n"
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

async def passive_income_job(context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT room_num, level FROM rooms WHERE user_id=?", (uid,)) as cur2:
                rooms = await cur2.fetchall()
            if not rooms:
                continue
            rooms_list = [{"room_num": r[0], "level": r[1]} for r in rooms]
            half_income = sum(get_current_income(r["room_num"], r["level"]) for r in rooms_list) // 2
            if half_income <= 0:
                continue
            limit = get_balance_limit(rooms_list)
            async with db.execute("SELECT balance, bunker_broken FROM users WHERE user_id=?", (uid,)) as cur3:
                row = await cur3.fetchone()
            if not row:
                continue
            current, broken = row[0], row[1] or 0
            half_income = sum(get_current_income(r["room_num"], r["level"]) for r in rooms_list) // 2
            if broken:
                half_income = half_income // 2
            # Проверяем бензин
            async with db.execute("SELECT fuel FROM users WHERE user_id=?", (uid,)) as cur_f:
                fuel_row = await cur_f.fetchone()
            has_fuel = fuel_row and fuel_row[0] > 0
            if not has_fuel:
                continue  # Нет бензина — нет дохода
            add = min(half_income, max(0, limit - current))
            if add > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id=?",
                    (add, uid)
                )
        await db.commit()
# ── Бочки ─────────────────────────────────────────────────────────────────────

async def get_barrels(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM barrels WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return {"user_id": user_id, "barrel_1": 0, "barrel_2": 0, "barrel_3": 0}

async def ensure_barrels(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO barrels (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def handle_barrels_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_barrels(uid)
    b = await get_barrels(uid)
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот твои бочки:\n"
        f"🛢 1. Обычная бочка: {b['barrel_1']} шт.\n"
        f"🏺 2. Бронзовая бочка: {b['barrel_2']} шт.\n"
        f"⚱️ 3. Золотая бочка: {b['barrel_3']} шт.\n\n"
        f"🧾 Цены на бочки:\n"
        f"   🛢 Обычная бочка — 5,000 кр.\n"
        f"   🏺 Бронзовая бочка — 30,000 кр.\n"
        f"   ⚱️ Золотая бочка — 30 BB-coins\n\n"
        f"ℹ️ Бочку можно купить командой — <code>Купить бочку</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_buy_barrel(update: Update, user: dict, parts: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_barrels(uid)
    # parts — это raw.split(), индексы: 0="купить", 1="бочку", 2=номер, 3=кол-во
    if len(parts) < 4:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно купить бочки!\n"
            f"Курс бочек — <code>Бочки</code>\n\n"
            f"Пример: <code>Купить бочку [номер] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        num = int(parts[2])
        qty = int(parts[3])
    except:
        await update.message.reply_text("Неверный формат. Пример: Купить бочку 1 5", parse_mode=ParseMode.HTML)
        return
    if num not in (1, 2, 3):
        await update.message.reply_text(f"{user_link(uid, username)}, номер бочки от 1 до 3!", parse_mode=ParseMode.HTML)
        return
    if qty <= 0:
        return
    prices = {1: 5000, 2: 30000}
    if num in prices:
        cost = prices[num] * qty
        if user["balance"] < cost:
            await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        col = f"barrel_{num}"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE users SET balance = balance - ? WHERE user_id=?", (cost, uid))
            await db.execute(f"UPDATE barrels SET {col} = {col} + ? WHERE user_id=?", (qty, uid))
            await db.commit()
        await update.message.reply_text(
            f"{user_link(uid, username)}, ты купил(-а) {qty} шт. бочки #{num} за {fmt_smart(cost)} кр.!",
            parse_mode=ParseMode.HTML
        )
    else:
        # Золотая бочка — за BB-coins
        cost_bb = 30 * qty
        if user["bb_coins"] < cost_bb:
            await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно BB-coins!", parse_mode=ParseMode.HTML)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bb_coins = bb_coins - ? WHERE user_id=?", (cost_bb, uid))
            await db.execute("UPDATE barrels SET barrel_3 = barrel_3 + ? WHERE user_id=?", (qty, uid))
            await db.commit()
        await update.message.reply_text(
            f"{user_link(uid, username)}, ты купил(-а) {qty} шт. золотой бочки за {cost_bb} BB-coins!",
            parse_mode=ParseMode.HTML
        )

async def handle_open_barrel(update: Update, user: dict, parts: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_barrels(uid)
    # parts индексы: 0="открыть", 1="бочку", 2=номер, 3=кол-во
    if len(parts) < 3:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно открыть бочку!\n\n"
            f"Пример: <code>Открыть бочку [номер] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        num = int(parts[2])
        qty = int(parts[3]) if len(parts) >= 4 else 1
    except:
        await update.message.reply_text("Неверный формат. Пример: Открыть бочку 1 5", parse_mode=ParseMode.HTML)
        return

    if num not in (1, 2, 3):
        await update.message.reply_text(f"{user_link(uid, username)}, номер бочки от 1 до 3!", parse_mode=ParseMode.HTML)
        return

    max_open = get_vip_barrel_limit(vip)
    qty = min(qty, max_open)

    b = await get_barrels(uid)
    col = f"barrel_{num}"
    available = b[col]
    if available <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя нет бочки #{num}!", parse_mode=ParseMode.HTML)
        return
    qty = min(qty, available)

    total_income = await get_total_income(uid)

    # Считаем награды
    total_coins = 0
    total_rating = 0
    total_stim = 0
    total_weapon = 0

    barrel_names = {1: ("🛢 Обычную бочку", 1000, 4500), 2: ("🏺 Бронзовую бочку", 5000, 30000), 3: ("⚱️ Золотую бочку", 0, 0)}
    bname = barrel_names[num][0]

    for _ in range(qty):
        if num == 1:
            total_coins += random.randint(1000, 4500)
            if random.random() < 0.20:
                total_rating += random.randint(1, 2)
            if random.random() < 0.10:
                total_stim += 1
            if random.random() < 0.10:
                total_weapon += 1
        elif num == 2:
            total_coins += random.randint(5000, 30000)
            if random.random() < 0.25:
                total_rating += random.randint(1, 2)
            if random.random() < 0.10:
                total_stim += random.randint(1, 2)
            if random.random() < 0.10:
                total_weapon += random.randint(1, 2)
        else:
            # Золотая — 300% от дохода в час
            total_coins += int(total_income * 3.0)
            total_rating += random.randint(5, 50)
            total_stim += random.randint(5, 20)
            total_weapon += random.randint(5, 20)

    # Обновляем БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE barrels SET {col} = {col} - ? WHERE user_id=?", (qty, uid))
        await db.execute("UPDATE users SET balance = balance + ?, rating = rating + ? WHERE user_id=?",
                         (total_coins, total_rating, uid))
        await db.commit()

    drops = [f"💰 {fmt_smart(total_coins)} крышек"]
    if total_rating > 0:
        drops.append(f"🏆 {total_rating} рейтинг")
    if total_stim > 0:
        drops.append(f"💉 {total_stim} стимулятора(-ов)")
    if total_weapon > 0:
        drops.append(f"🔫 {total_weapon} оружие(-я)")

    drops_text = "\n".join(drops)
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты открыл {bname} ({qty}шт.)\n"
        f"📦 Тебе выпало:\n"
        f"<blockquote>{drops_text}</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Починить бункер ───────────────────────────────────────────────────────────

async def handle_repair_bunker(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    broken = user.get("bunker_broken", 0)
    if not broken:
        await update.message.reply_text(
            f"{user_link(uid, username)}, твой бункер в порядке, ничего чинить не нужно!",
            parse_mode=ParseMode.HTML
        )
        return
    total_income = await get_total_income(uid)
    repair_cost = int(total_income * 0.20)
    if user["balance"] < repair_cost:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя недостаточно крышек для починки бункера!\n"
            f"Необходимо: {fmt_smart(repair_cost)} кр.",
            parse_mode=ParseMode.HTML
        )
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ?, bunker_broken = 0 WHERE user_id=?",
                         (repair_cost, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно исправил(-а) происшествие в бункере за {fmt_smart(repair_cost)} кр.!",
        parse_mode=ParseMode.HTML
    )


# ── Теплица ───────────────────────────────────────────────────────────────────

async def get_greenhouse(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM greenhouse WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def ensure_greenhouse(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO greenhouse (user_id) VALUES (?)", (user_id,))
        await db.commit()

def get_available_crops(exp: int):
    return [name for name, data in CROPS.items() if data["exp_req"] <= exp]

async def handle_my_greenhouse(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_greenhouse(uid)
    gh = await get_greenhouse(uid)
    exp = gh["exp"]
    water = gh["water"]
    water_limit = get_vip_water_limit(vip)
    selected = gh["selected_crop"]
    available = get_available_crops(exp)
    if selected not in available:
        selected = "картошка"

    # Склад
    stock_lines = []
    for crop, data in CROPS.items():
        amount = gh.get(data["col"], 0)
        if amount > 0:
            stock_lines.append(f"   {data['emoji']} {crop.capitalize()} — {amount} шт.")
    stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"

    crop_emoji = CROPS[selected]["emoji"]
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, информация о твоей теплице:\n"
        f"  ⭐️ Опыт: {fmt_smart(exp)}\n"
        f"  💧 Вода: {water}/{water_limit} л.\n"
        f"  🪴 Тебе доступна: {selected}\n\n"
        f"📦 Твой склад:\n{stock_text}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔀 Выбрать сорт", callback_data=f"gh_select_{uid}")],
        [InlineKeyboardButton(f"💧 Вырастить {crop_emoji}", callback_data=f"gh_grow_{uid}_1")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_greenhouse_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды выращиваемых сортов:\n"
        f"   🥔 Картошка — доступна сразу\n"
        f"   🥕 Морковь — 500 опыта\n"
        f"   🍚 Рис — 2.000 опыта\n"
        f"   🧄 Чеснок — 5.000 опыта\n"
        f"   🍠 Свекла — 10.000 опыта\n"
        f"   🥒 Огурец — 25.000 опыта\n"
        f"   🥬 Капуста — 40.000 опыта\n"
        f"   🫘 Фасоль — 60.000 опыта\n"
        f"   🍅 Помидор — 100.000 опыта\n"
        f"   🍆 Баклажан — 125.000 опыта"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_greenhouse_rate(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды выращиваемых сортов и их цена:\n"
        f"   🥔 Картошка — 100 крышек/шт\n"
        f"   🥕 Морковь — 200 крышек/шт\n"
        f"   🍚 Рис — 600 крышек/шт\n"
        f"   🧄 Чеснок — 1,000 крышек/шт\n"
        f"   🍠 Свекла — 1,400 крышек/шт\n"
        f"   🥒 Огурец — 2,500 крышек/шт\n"
        f"   🥬 Капуста — 3,500 крышек/шт\n"
        f"   🫘 Фасоль — 5,000 крышек/шт\n"
        f"   🍅 Помидор — 10,000 крышек/шт\n"
        f"   🍆 Баклажан — 20,000 крышек/шт"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_grow(update: Update, user: dict, parts_raw: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    await ensure_greenhouse(uid)
    gh = await get_greenhouse(uid)

    CROP_NAMES = list(CROPS.keys())
    if len(parts_raw) < 2:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно вырастить определённый сорт!\n"
            f"Виды культур — {', '.join(CROP_NAMES)}\n\n"
            f"Пример: <code>Вырастить [название сорта] [кол-во]</code>",
            parse_mode=ParseMode.HTML
        )
        return

# Словарь для падежей: "картошку" -> "картошка"
    CROP_FORMS = {
        "картошку": "картошка", "картошки": "картошка", "картошка": "картошка",
        "морковь": "морковь", "морковку": "морковь", "моркови": "морковь",
        "рис": "рис", "риса": "рис",
        "чеснок": "чеснок", "чеснока": "чеснок",
        "свеклу": "свекла", "свеклы": "свекла", "свекла": "свекла",
        "огурец": "огурец", "огурца": "огурец",
        "капусту": "капуста", "капусты": "капуста", "капуста": "капуста",
        "фасоль": "фасоль", "фасоли": "фасоль",
        "помидор": "помидор", "помидора": "помидор", "помидоры": "помидор",
        "баклажан": "баклажан", "баклажана": "баклажан",
    }
    CROP_FORMS_ACC = {
    "картошка": "картошку", "морковь": "морковь", "рис": "рис",
    "чеснок": "чеснок", "свекла": "свеклу", "огурец": "огурец",
    "капуста": "капусту", "фасоль": "фасоль", "помидор": "помидор",
    "баклажан": "баклажан",}
    raw_crop = parts_raw[1].lower()
    crop_name = CROP_FORMS.get(raw_crop, raw_crop)
    if crop_name not in CROPS:
        await update.message.reply_text(
            f"{user_link(uid, username)}, такого сорта нет! \n\nДоступны: {', '.join(CROP_NAMES)}",
            parse_mode=ParseMode.HTML
        )
        return

    crop_data = CROPS[crop_name]
    if gh["exp"] < crop_data["exp_req"]:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя недостаточно опыта для выращивания {crop_name}!\n"
            f"Нужно: {fmt_smart(crop_data['exp_req'])} опыта",
            parse_mode=ParseMode.HTML
        )
        return

    max_qty = get_vip_grow_limit(vip)
    try:
        qty = int(parts_raw[2]) if len(parts_raw) >= 3 else 1
    except:
        qty = 1
    qty = max(1, min(qty, max_qty))

    water_limit = get_vip_water_limit(vip)
    water = gh["water"]
    if water < qty:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя недостаточно воды!\n"
            f"Есть: {water}/{water_limit} 💧",
            parse_mode=ParseMode.HTML
        )
        return

    total_crop = 0
    total_exp = 0
    for _ in range(qty):
        total_crop += random.randint(1, 2)
        total_exp += random.randint(1, 4)

    col = crop_data["col"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE greenhouse SET {col} = {col} + ?, exp = exp + ?, water = water - ? WHERE user_id=?",
            (total_crop, total_exp, qty, uid)
        )
        await db.commit()

    gh = await get_greenhouse(uid)
    water_left = gh["water"]
    await update.message.reply_text(
        f"🙎‍♂️ {user_link(uid, username)}, ты успешно вырастил(-а) {CROP_FORMS_ACC.get(crop_name, crop_name)}!\n"
        f"Получено: {total_crop} {crop_data['emoji']}, {total_exp} опыта\n"
        f"Потрачено: {qty} 💧\n"
        f"Осталось воды: {water_left}/{water_limit} 💧",
        parse_mode=ParseMode.HTML
    )

async def handle_sell_crop(update: Update, user: dict, parts_raw: list):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_greenhouse(uid)

    CROP_NAMES = list(CROPS.keys())
    if len(parts_raw) < 2:
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, этой командой можно продать плоды!\n"
            f"Курс — <code>Курс теплица</code>\n\n"
            f"Пример: <code>Продать [название] [кол-во или всё]</code>",
            parse_mode=ParseMode.HTML
        )
        return

    CROP_FORMS = {
        "картошку": "картошка", "картошки": "картошка", "картошка": "картошка",
        "морковь": "морковь", "морковку": "морковь", "моркови": "морковь",
        "рис": "рис", "риса": "рис",
        "чеснок": "чеснок", "чеснока": "чеснок",
        "свеклу": "свекла", "свеклы": "свекла", "свекла": "свекла",
        "огурец": "огурец", "огурца": "огурец",
        "капусту": "капуста", "капусты": "капуста", "капуста": "капуста",
        "фасоль": "фасоль", "фасоли": "фасоль",
        "помидор": "помидор", "помидора": "помидор", "помидоры": "помидор",
        "баклажан": "баклажан", "баклажана": "баклажан",
    }

    CROP_FORMS_ACC = {
    "картошка": "картошку", "морковь": "морковь", "рис": "рис",
    "чеснок": "чеснок", "свекла": "свеклу", "огурец": "огурец",
    "капуста": "капусту", "фасоль": "фасоль", "помидор": "помидор",
    "баклажан": "баклажан",}
    raw_crop = parts_raw[1].lower()
    crop_name = CROP_FORMS.get(raw_crop, raw_crop)
    if crop_name not in CROPS:
        return False

    gh = await get_greenhouse(uid)
    crop_data = CROPS[crop_name]
    col = crop_data["col"]
    available = gh.get(col, 0)

    if available <= 0:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет {crop_name}!", parse_mode=ParseMode.HTML
        )
        return

    if len(parts_raw) >= 3:
        if parts_raw[2].lower() == "всё" or parts_raw[2].lower() == "все":
            qty = available
        else:
            try:
                qty = int(parts_raw[2])
            except:
                qty = 1
    else:
        qty = available

    qty = min(qty, available)
    earnings = qty * crop_data["sell_price"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE greenhouse SET {col} = {col} - ? WHERE user_id=?", (qty, uid)
        )
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (earnings, uid))
        await db.commit()

    await update.message.reply_text(
        f"🙎‍♂️ {user_link(uid, username)}, ты продал(-а) {qty} {crop_data['emoji']} {crop_name} за {fmt_smart(earnings)} кр.!",
        parse_mode=ParseMode.HTML
    )


# ── Шахта ─────────────────────────────────────────────────────────────────────

async def get_mine(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM mine WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
    return None

async def ensure_mine(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO mine (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def handle_mine_info(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот доступные кирки:\n\n"
        f"  ⛏️ Каменная кирка — 30,000 крышек\n"
        f"      Запас прочности — 1\n"
        f"  ⛏️ Железная кирка — 200,000 крышек\n"
        f"      Запас прочности — 3\n"
        f"  💎 Алмазная кирка — 1,000,000 крышек\n"
        f"      Запас прочности — 5\n\n"
        f"Ресурсы и шансы на их добычу:\n"
        f"  🏜️ Песок — 100/100/100%\n"
        f"  ◾️ Уголь — 85/100/100%\n"
        f"  🚂 Железо — 50/90/100%\n"
        f"  🟠 Медь — 30/50/80%\n"
        f"  🥈 Серебро — 0/40/70%\n"
        f"  💎 Алмаз — 0/30/60%\n"
        f"  ☢️ Уран — 0/10/40%\n\n"
        f"Купить кирку: <code>Купить кирку [1/2/3]</code>\n"
        f"Курс: <code>Курс шахта</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_my_mine(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"🙎‍♂️ {user_link(uid, username)}, у тебя нет шахты!\nНужна комната 12.",
            parse_mode=ParseMode.HTML
        )
        return
    await ensure_mine(uid)
    m = await get_mine(uid)
    pickaxe_id = m["pickaxe"]
    if pickaxe_id == 0:
        pickaxe_name = "Нет кирки"
    else:
        pickaxe_name = PICKAXES[pickaxe_id]["name"]
    durability = m["durability"]
    depth = m["depth"]

    stock_lines = []
    for key, res in MINE_RESOURCES.items():
        amount = m.get(res["col"], 0)
        if amount > 0:
            stock_lines.append(f"   {res['emoji']} {res['name']} — {amount} кг.")
    stock_text = "\n".join(stock_lines) if stock_lines else "   *пусто*"

    text = (
        f"🙎‍♂️ {user_link(uid, username)}, информация о твоей шахте:\n"
        f"  ⛏️ Кирка: {pickaxe_name}\n"
        f"  ⚙️ Прочность: {durability}\n"
        f"  📉 Уровень погружения: {depth} м.\n\n"
        f"📦 Твой склад:\n{stock_text}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ Копать", switch_inline_query_current_chat="Копать")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_mine_rate(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, вот виды ресурсов и их цена:\n"
        f"   🏜️ Песок — 2,000 кр/кг\n"
        f"   ◾️ Уголь — 5,000 кр/кг\n"
        f"   🚂 Железо — 8,000 кр/кг\n"
        f"   🟠 Медь — 12,000 кр/кг\n"
        f"   🥈 Серебро — 18,000 кр/кг\n"
        f"   💎 Алмаз — 60,000 кр/кг\n"
        f"   ☢️ Уран — 150,000 кр/кг"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

def get_mine_chances_by_depth(depth: int, pickaxe_idx: int) -> dict:
    """Возвращает шансы ресурсов в зависимости от глубины и кирки."""
    chances = {}
    # Песок
    if depth < 300:
        chances["sand"] = min(100, MINE_CHANCES["sand"][pickaxe_idx])
    # Уголь
    if depth < 40:
        coal_base = 0
    elif depth < 80:
        coal_base = 30
    elif depth < 150:
        coal_base = 60
    elif depth < 300:
        coal_base = 50
    else:
        coal_base = 40
    if coal_base > 0:
        chances["coal"] = min(coal_base, MINE_CHANCES["coal"][pickaxe_idx])
    # Железо
    if depth >= 80:
        iron_base = 20 if depth < 150 else (30 if depth < 300 else 40)
        chances["iron"] = min(iron_base, MINE_CHANCES["iron"][pickaxe_idx])
    # Медь
    if depth >= 150:
        copper_base = 30 if depth < 300 else 25
        chances["copper"] = min(copper_base, MINE_CHANCES["copper"][pickaxe_idx])
    # Серебро
    if depth >= 150:
        silver_base = 30 if depth < 300 else 35
        chances["silver"] = min(silver_base, MINE_CHANCES["silver"][pickaxe_idx])
    # Алмаз
    if depth >= 150:
        if depth < 200:
            diamond_base = 10
        elif depth < 300:
            diamond_base = 20
        elif depth < 400:
            diamond_base = 30
        else:
            diamond_base = 35
        chances["diamond"] = min(diamond_base, MINE_CHANCES["diamond"][pickaxe_idx])
    # Уран
    if depth >= 500:
        chances["uranium"] = min(20, MINE_CHANCES["uranium"][pickaxe_idx])
    return chances

DIG_PENDING = {}  # uid -> {"resource": key, "chance": N, "bet": None}

async def handle_dig(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет шахты! Нужна комната 12.",
            parse_mode=ParseMode.HTML
        )
        return
    await ensure_mine(uid)
    m = await get_mine(uid)
    if m["pickaxe"] == 0 or m["durability"] <= 0:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет кирки или она сломана!\n"
            f"Купи кирку: <code>Купить кирку [1/2/3]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    pickaxe_idx = m["pickaxe"] - 1
    depth = m["depth"]
    chances = get_mine_chances_by_depth(depth, pickaxe_idx)
    if not chances:
        await update.message.reply_text(
            f"{user_link(uid, username)}, на этой глубине ничего не найти. Копай глубже!",
            parse_mode=ParseMode.HTML
        )
        return
    # Выбираем случайный ресурс с учётом шансов
    keys = list(chances.keys())
    weights = [chances[k] for k in keys]
    chosen_key = random.choices(keys, weights=weights, k=1)[0]
    chosen_res = MINE_RESOURCES[chosen_key]
    chance_val = chances[chosen_key]

    DIG_PENDING[uid] = {"resource": chosen_key, "chance": chance_val}

    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты нашёл {chosen_res['emoji']} {chosen_res['name']}.\n"
        f"Ты можешь его выкопать с вероятностью {chance_val}%\n"
        f"📉 Глубина: {depth} м."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ Копать", callback_data=f"dig_do_{uid}"),
         InlineKeyboardButton("🚬 Пропустить", callback_data=f"dig_skip_{uid}")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_buy_pickaxe(update: Update, user: dict, pickaxe_num: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if not await has_room(uid, 12):
        await update.message.reply_text(
            f"{user_link(uid, username)}, для покупки кирки нужна комната 12 (Шахта)!",
            parse_mode=ParseMode.HTML
        )
        return
    if pickaxe_num not in PICKAXES:
        await update.message.reply_text(f"{user_link(uid, username)}, номер кирки от 1 до 3!", parse_mode=ParseMode.HTML)
        return
    pk = PICKAXES[pickaxe_num]
    if user["balance"] < pk["price"]:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    await ensure_mine(uid)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (pk["price"], uid))
        await db.execute("UPDATE mine SET pickaxe = ?, durability = ? WHERE user_id=?",
                         (pickaxe_num, pk["durability"], uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты купил(-а) {pk['emoji']} {pk['name']} за {fmt_smart(pk['price'])} кр.!",
        parse_mode=ParseMode.HTML
    )

async def handle_sell_mine_resource(update: Update, user: dict, res_key: str, qty_str: str) -> bool:
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    await ensure_mine(uid)
    m = await get_mine(uid)
    if res_key not in MINE_RESOURCES:
        return False
    res = MINE_RESOURCES[res_key]
    available = m.get(res["col"], 0)
    if available <= 0:
        await update.message.reply_text(
            f"{user_link(uid, username)}, у тебя нет {res['name'].lower()}!",
            parse_mode=ParseMode.HTML
        )
        return True
    if qty_str.lower() in ("всё", "все"):
        qty = available
    else:
        try:
            qty = int(qty_str)
        except:
            qty = available
    qty = min(qty, available)
    earnings = qty * res["sell"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE mine SET {res['col']} = {res['col']} - ? WHERE user_id=?", (qty, uid))
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (earnings, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты продал(-а) {qty} кг. {res['emoji']} {res['name']} за {fmt_smart(earnings)} кр.!",
        parse_mode=ParseMode.HTML
    )
    return True


# ── Казино (игры с картами — Очко) ───────────────────────────────────────────

async def handle_ochko_start(update: Update, user: dict, bet: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if user["balance"] < bet:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    if bet <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, ставка должна быть больше 0!", parse_mode=ParseMode.HTML)
        return

    deck = CARD_DECK.copy()
    random.shuffle(deck)

    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Сохраняем состояние игры в user_data
    context_key = f"ochko_{uid}"
    game_state = {
        "bet": bet,
        "deck": deck,
        "player": player_hand,
        "dealer": dealer_hand,
        "username": username,
    }

    # Списываем ставку
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, uid))
        await db.commit()

    pval = hand_value(player_hand)
    dval = hand_value(dealer_hand)

    text = (
        f"♣️ {user_link(uid, username)}, ты запустил игру 21\n"
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
    msg = await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    OCHKO_GAMES[uid] = {**game_state, "msg_id": msg.message_id, "chat_id": update.message.chat_id}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle referral
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
        except:
            pass

    await update.message.reply_text(
        "Добро пожаловать в игру 'Бункер'! Чтобы разобраться как играть, напишите Помощь\n\n"
        "Так же у нас есть чат, где вы сможете весело провести время с остальными https://t.me/bfgbunker_chat",
        disable_web_page_preview=True
    , parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] if user else (update.effective_user.first_name or "Игрок")
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, выберите категорию:\n"
        "   📚 Основное\n"
        "   🎮 Игры\n"
        "   🏄‍♀️ Активности\n"
        "   💬 Чаты\n\n"
        "💬 Так же у нас есть общая беседа №1\n"
        "🆘 По всем вопросам - @Alkyrin"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=help_main_keyboard(), parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=help_main_keyboard(), parse_mode=ParseMode.HTML)


async def cmd_bunker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    text = await build_bunker_text(uid)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_room(update: Update, context: ContextTypes.DEFAULT_TYPE, room_num: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    vip = user.get("vip", 0)
    if room_num is None:
        await update.message.reply_text("Укажите номер комнаты, например: К 1")
        return
    if not await has_room(uid, room_num):
        await update.message.reply_text(f"{user_link(uid, user['username'])}, у тебя нет данной комнаты.\nТы можешь её купить командой: Купить комнату [номер комнаты].", parse_mode=ParseMode.HTML)
        return
    context.user_data[f"room_{room_num}_bottles"] = False
    text = await build_room_text(uid, room_num, use_bottles=False)
    if text:
        await update.message.reply_text(text, reply_markup=room_keyboard(room_num, use_bottles=False, vip=vip), parse_mode=ParseMode.HTML)


async def cmd_rooms_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    unlock = [
        (1, "со старта"), (2, "со старта"), (3, "со старта"), (4, "со старта"),
        (5, "от 5 🧍"), (6, "от 12 🧍"), (7, "от 24 🧍"), (8, "от 40 🧍"),
        (9, "от 80 🧍"), (10, "от 130 🧍"), (11, "от 220 🧍"), (12, "от 360 🧍"),
        (13, "от 500 🧍"), (14, "от 720 🧍"), (15, "от 1000 🧍"),
        (16, "от 1400 🧍"), (17, "от 2000 🧍"), (18, "от 3500 🧍"), (19, "от 5000 🧍"),
    ]
    lines = [f"🙎‍♂️ {user_link(user['user_id'], user['username'])}\n"]
    for rn, cond in unlock:
        emoji = NUM_EMOJIS.get(rn, f"{rn}.")
        lines.append(f"{emoji} {ROOMS_DATA[rn]['name']} - {cond}")
    lines.append("\nℹ️ Купить комнату можно командой - Купить комнату [номер]")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_let_in(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    queue = user["queue"]
    if amount is None or amount <= 0:
        await update.message.reply_text(f"{user_link(uid, username)}, этой командой можно впустить людей в бункер!\nСледите за уровнями комнат!\n\nПример: Впустить [кол-во человек]", parse_mode=ParseMode.HTML)
        return
    if amount > queue:
        await update.message.reply_text(f"{user_link(uid, username)}, недостаточно людей, в очереди: {queue} чел.", parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET people = people + ?, queue = queue - ? WHERE user_id = ?",
            (amount, amount, uid)
        )
        await db.commit()
    user = await get_user(uid)
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты впустил(-а) {amount} человек(а) в бункер!"
    , parse_mode=ParseMode.HTML)


async def cmd_buy_room(update: Update, context: ContextTypes.DEFAULT_TYPE, room_num: int = None):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    username = user["username"] or "Игрок"
    rooms = await get_rooms(uid)
    owned = {r["room_num"] for r in rooms}

    if room_num is None:
        await update.message.reply_text(f"{user_link(uid, username)}, этой командой можно купить комнату!\nСписок комнат можно посмотреть командой Список комнат\n\nПример: Купить комнату [номер комнаты]", parse_mode=ParseMode.HTML)
        return

    if room_num < 5 or room_num > 19:
        await update.message.reply_text(f"{user_link(uid, username)}, можно купить комнаты с 5 по 19.", parse_mode=ParseMode.HTML)
        return

    if room_num in owned:
        await update.message.reply_text(f"{user_link(uid, username)}, у вас уже есть эта комната!", parse_mode=ParseMode.HTML)
        return

    req_people = ROOMS_DATA[room_num]["unlock_people"]
    if user["people"] < req_people:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя недостаточно людей в бункере!", parse_mode=ParseMode.HTML)
        return

    price = ROOM_BUY_PRICES[room_num]

    if user["balance"] < price:
        await update.message.reply_text(
            f"{user_link(uid, username)}, недостаточно крышек!"
        , parse_mode=ParseMode.HTML)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, uid))
        await db.execute("INSERT INTO rooms (user_id, room_num, level) VALUES (?, ?, 1)", (uid, room_num))
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно купил(-а) комнату: {ROOMS_DATA[room_num]['name']}!\n"
    , parse_mode=ParseMode.HTML)


async def do_room_upgrade(user_id: int, room_num: int, levels: int, use_bottles: bool) -> str:
    user = await get_user(user_id)
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)

    vip_requirements = {20: 1, 100: 2, 1000: 3, 5000: 4}
    required_vip = vip_requirements.get(levels, 0)
    if required_vip > 0 and vip < required_vip:
        vip_names = {1: "VIP1", 2: "VIP2", 3: "VIP3", 4: "VIP4"}
        return f"Эта функция доступна только для обладателей статуса {vip_names[required_vip]} и выше!"

    if not await has_room(user_id, room_num):
        return f"{user_link(user_id, username)}, у вас нет комнаты №{room_num}."

    current_level = await get_room_level(user_id, room_num)
    balance = user["balance"]
    bottles = user["bottles"]

    BOTTLE_TO_COINS = 10000

    total_cost = sum(get_upgrade_cost(room_num, current_level + i) for i in range(levels))

    if use_bottles:
        total_cost_bottles = total_cost / BOTTLE_TO_COINS
        if bottles < total_cost_bottles:
            return f"Недостаточно бутылок! Нужно {fmt_bottles(total_cost_bottles)} 🍾."
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bottles = bottles - ? WHERE user_id = ?", (total_cost_bottles, user_id))
            await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?",
                             (levels, user_id, room_num))
            await db.commit()
    else:
        if balance < total_cost:
            return f"Недостаточно крышек! Нужно {fmt_smart(total_cost)} кр."
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
            await db.execute("UPDATE rooms SET level = level + ? WHERE user_id = ? AND room_num = ?",
                             (levels, user_id, room_num))
            await db.commit()

    new_level = current_level + levels
    new_income = get_current_income(room_num, new_level)

    # Шанс поломки бункера
    break_chances = {1: 1, 5: 3, 20: 10, 100: 15, 1000: 25, 5000: 25}
    break_chance = break_chances.get(levels, 0)
    broke = random.randint(1, 100) <= break_chance

    if broke:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET bunker_broken = 1 WHERE user_id=?", (user_id,))
            await db.commit()
        # Возвращаем два значения: сообщение об улучшении и флаг пожара
        return f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня за {fmt_smart(total_cost)} кр.", True

    return (
        f"Ты улучшил(-а) '{ROOMS_DATA[room_num]['name']}' до {new_level} уровня\n"
        f"за {fmt_smart(total_cost)} кр."
    ), False


async def queue_refill_job(context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE queue < 5") as cur:
            users = await cur.fetchall()
        for (uid,) in users:
            radio_level = 0
            async with db.execute("SELECT level FROM rooms WHERE user_id=? AND room_num=8", (uid,)) as cur2:
                row = await cur2.fetchone()
                if row:
                    radio_level = row[0]
            chance = 0.55 + radio_level * 0.005
            if random.random() < chance:
                await db.execute("UPDATE users SET queue = MIN(queue + 1, 5) WHERE user_id = ?", (uid,))
        await db.commit()


# ── Rating handlers ──────────────────────────────────────────────────────────

async def handle_rating(update: Update, user: dict):
    username = user["username"] or "Игрок"
    rating = user.get("rating", 0)
    await update.message.reply_text(f"{user_link(user['user_id'], username)}, твой рейтинг {fmt_smart(rating)} 🏆", parse_mode=ParseMode.HTML)


async def handle_buy_rating(update: Update, user: dict, amount: int):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    cost = amount * RATING_BUY_PRICE
    if user["balance"] < cost:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя не достаточно денег!", parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ?, rating = rating + ? WHERE user_id = ?",
                         (cost, amount, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно купил(-а) {fmt_smart(amount)} рейтинг за {fmt_smart(cost)} крышек!"
    , parse_mode=ParseMode.HTML)


async def handle_sell_rating(update: Update, user: dict, amount: int):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    if user.get("rating", 0) < amount:
        await update.message.reply_text(f"{user_link(uid, username)}, у тебя не достаточно рейтинга!", parse_mode=ParseMode.HTML)
        return
    earn = amount * RATING_SELL_PRICE
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ?, rating = rating - ? WHERE user_id = ?",
                         (earn, amount, uid))
        await db.commit()
    await update.message.reply_text(
        f"{user_link(uid, username)}, ты успешно продал(-а) {fmt_smart(amount)} рейтинг за {fmt_smart(earn)} крышек!"
    , parse_mode=ParseMode.HTML)


# ── Nickname change ──────────────────────────────────────────────────────────

async def handle_change_nick(update: Update, user: dict, new_nick: str):
    uid = update.effective_user.id
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    max_len = {0: 20, 1: 25, 2: 30, 3: 40, 4: 50}.get(vip, 20)
    if len(new_nick) > max_len:
        await update.message.reply_text(
            f"{user_link(uid, username)}, ник слишком длинный! Максимум {max_len} символов."
        , parse_mode=ParseMode.HTML)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_nick, uid))
        await db.commit()
    await update.message.reply_text(f"{user_link(uid, username)}, ты успешно изменил(-а) имя на {new_nick}!", parse_mode=ParseMode.HTML)


# ── Balance / bb command ─────────────────────────────────────────────────────

async def handle_balance(update: Update, user: dict):
    rooms = await get_rooms(user["user_id"])
    balance_limit = get_balance_limit(rooms)
    username = user["username"] or "Игрок"
    bal_fmt = fmt_smart(user['balance'])
    lim_fmt = fmt_smart(balance_limit)
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"💰 Баланс: {bal_fmt}/{lim_fmt} кр.\n"
        f"🍾 Бутылки: {int(user['bottles'])}\n"
        f"🪙 BB-coins: {fmt_smart(user['bb_coins'])}\n"
        f"🏆 Рейтинг: {fmt_smart(user.get('rating', 0))}"
    )
    await update.message.reply_text(text, reply_to_message_id=update.message.message_id, parse_mode=ParseMode.HTML)


# ── Donate ───────────────────────────────────────────────────────────────────

def donate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Купить 🪙 BBCoins", url="https://t.me/Alkyrin")],
        [InlineKeyboardButton("💰 Сайт для доната 💰", url="https://t.me/Alkyrin")],
    ])


async def handle_donate(update: Update, user: dict):
    username = user["username"] or "Игрок"
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"Команды:\n"
        f"   ⚖️ <code>Донат курс</code>\n"
        f"   🪙 Донат купить крышки [кол. тысяч]\n"
        f"   💹 Донат купить рейтинг [кол. рейтинга]\n"
        f"   👨‍👨‍👦‍👦 Донат купить людей [кол. людей]\n"
        f"   🎫 Донат купить вип [уровень]\n"
        f"   🚘 Донат купить авто [4/5/6]\n\n"
        f"Доп. контакты для доната - Alkyrin\n\n"
        f"<blockquote>🔥 На сайте действует скидка на донат 50% 🔥</blockquote>"
    )
    await update.message.reply_text(text, reply_markup=donate_keyboard(), parse_mode=ParseMode.HTML)


async def handle_donate_rate(update: Update, user: dict):
    username = user["username"] or "Игрок"
    # 1% of total income
    total_income = await get_total_income(user["user_id"])
    coin_rate = max(1, int(total_income * 0.05))
    text = (
        f"🙎‍♂️ {user_link(user['user_id'], username)}\n"
        f"Курс обмена BB-coins:\n"
        f"   🪙 1 BB-coins -> {fmt_smart(coin_rate)} крышек\n"
        f"   💹 10 BB-coins -> 1 рейтинг\n"
        f"   👨‍👨‍👦‍👦 5 BB-coins -> 1 человек\n"
        f"   ⚡️ 200 BB-coins -> VIP1\n"
        f"   🔥 600 BB-coins -> VIP2\n"
        f"   💎 1200 BB-coins -> VIP3\n"
        f"   ⭐️ 2000 BB-coins -> VIP4\n"
        f"   🚘 250/350/450 BB-coins -> Авто 4/5/6\n\n"
        f"Курс покупки BB-coins:\n"
        f"  1 ⭐️ -> 1 BB-coins\n"
        f"<blockquote>🔥 Действует скидка на донат 50% 🔥\n\n"
        f"При покупке VIP4 если у вас есть VIP3, цена будет составлять 800 BB-coins 🔥</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Statuses ─────────────────────────────────────────────────────────────────

async def handle_statuses(update: Update, user: dict):
    username = user["username"] or "Игрок"
    text = (
        f"👑 Информация о статусах 👑\n\n"
        f"⚡️ VIP1 ⚡️ (200 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Увеличенный шанс в азартных играх\n"
        f" - Улучшения комнаты на 20 уровней\n"
        f" - 150 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 5.000\n"
        f" - Лимит на открытие бочек 5🛢\n"
        f" - Длина ника до 25 символов\n"
        f" - Буст дохода +1%\n"
        f" - Выращивание в теплице до 5 растений за раз 🌱"
        f"</blockquote>\n"
        f"🔥 VIP2 🔥 (600 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 14/11/8/5/4 минуты\n"
        f" - Улучшения комнаты на 100 уровней\n"
        f" - 150 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 8.000\n"
        f" - Лимит воды увеличен до 50💧\n"
        f" - Лимит на открытие бочек 10🛢\n"
        f" - Длина ника до 30 символов\n"
        f" - Буст дохода +2%\n"
        f" - Выращивание в теплице до 10 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 45 сек"
        f"</blockquote>\n"
        f"💎 VIP3 💎 (1200 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - Ещё более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 13/10/7/4/3 минуты\n"
        f" - Улучшения комнаты на 1'000 уровней\n"
        f" - 200 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 15.000\n"
        f" - Лимит воды увеличен до 75💧\n"
        f" - Лимит на открытие бочек 25🛢\n"
        f" - Длина ника до 40 символов\n"
        f" - Просмотр ID юзеров\n"
        f" - Просмотр профилей других игроков\n"
        f" - Буст дохода +3%\n"
        f" - Выращивание в теплице до 15 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 30 сек\n"
        f"   ○ 100 ур. = 1 мин"
        f"</blockquote>\n"
        f"⭐️ VIP4 ⭐️ (2000 BB-Coins)\n"
        f"<blockquote expandable>"
        f" - 2 ежедневных бонуса в сутки\n"
        f" - Ещё более увеличенный шанс в азартных играх\n"
        f" - Ускоренный бур в шахте - 12/9/6/3/2 минуты\n"
        f" - Улучшения комнаты на 5'000 уровней\n"
        f" - 250 здоровья в пустоши\n"
        f" - Лимит переводов увеличен до 25.000\n"
        f" - Лимит воды увеличен до 100💧\n"
        f" - Лимит на открытие бочек 50🛢\n"
        f" - Длина ника до 50 символов\n"
        f" - Просмотр ID юзеров\n"
        f" - Просмотр профилей других игроков\n"
        f" - Возможность скрыть свой бункер\n"
        f" - Буст дохода +4%\n"
        f" - Выращивание в теплице до 20 растений за раз 🌱\n"
        f" - Сокращение времени на улучшение комнат:\n"
        f"   ○ 20 ур. = 20 сек\n"
        f"   ○ 100 ур. = 45 сек\n"
        f"   ○ 1000 ур. = 2 мин"
        f"</blockquote>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Promo codes ──────────────────────────────────────────────────────────────

async def handle_promo(update: Update, user: dict, promo: str):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    promo_lower = promo.lower()

    if promo_lower not in PROMO_CODES:
        await update.message.reply_text(f"{user_link(uid, username)}, такого промокода не существует!", parse_mode=ParseMode.HTML)
        return

    # Check if used
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM used_promos WHERE user_id=? AND promo=?", (uid, promo_lower)) as cur:
            if await cur.fetchone():
                await update.message.reply_text(f"{user_link(uid, username)}, этот промокод уже недействителен!", parse_mode=ParseMode.HTML)
                return

    promo_data = PROMO_CODES[promo_lower]
    reward_type = promo_data["reward_type"]
    amount = promo_data["amount"]

    async with aiosqlite.connect(DB_PATH) as db:
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
            reward_text = f"⭐️ {fmt_smart(amount)} опыта"
        else:
            reward_text = f"{fmt_smart(amount)} бонусов"

        await db.execute("INSERT OR IGNORE INTO used_promos (user_id, promo) VALUES (?, ?)", (uid, promo_lower))
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, тебе начислено:\n{reward_text}\n\n🧡 Приятной игры! 🧡"
    , parse_mode=ParseMode.HTML)


# ── Referral ─────────────────────────────────────────────────────────────────

async def handle_ref(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    # Count invited (simplified — not tracking in DB currently, show 0)
    invited = 0
    ref_link = f"https://t.me/darkhostrobot?start={uid}"
    share_link = f"https://t.me/share/url?url={ref_link}"
    text = (
        f"🙎‍♂️ {user_link(uid, username)}, ты пригласил(-а) {invited} 👨‍👧‍👦\n"
        f"🤭 Когда приглашенный человек купит 10 комнату, вы вдвоём получите по 20 BB-Coins 🪙"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Поделиться ссылкой ↩️", url=share_link)],
        [InlineKeyboardButton("Добавить бота в группу 🤖", url="https://t.me/darkhostrobot?startgroup")],
    ])
    await update.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode=ParseMode.HTML)


# ── Limits ───────────────────────────────────────────────────────────────────

async def handle_limits(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    transfer_limit = get_vip_transfer_limit(vip)
    await update.message.reply_text(
        f"🙎‍♂️ {user_link(uid, username)}, твои лимиты:\n"
        f"Передачи денег - {fmt_smart(transfer_limit)}/{fmt_smart(transfer_limit)}"
    , parse_mode=ParseMode.HTML)


# ── RP commands ───────────────────────────────────────────────────────────────

async def handle_rp_list(update: Update, user: dict):
    username = user["username"] or "Игрок"
    commands_list = list(RP_COMMANDS.keys())
    lines = [f"🙎‍♂️ {user_link(user['user_id'], username)}, все доступные РП команды:"]
    for i, cmd in enumerate(commands_list, 1):
        lines.append(f"{i}) {cmd.capitalize()}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_rp_action(update: Update, user: dict, action: str):
    username = user["username"] or "Игрок"
    past_form = RP_COMMANDS[action][0]
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(f"{user_link(user['user_id'], username)}, ты должен ответить на сообщение!", parse_mode=ParseMode.HTML)
        return
    target_uid = reply.from_user.id
    target_user = await get_user(target_uid)
    target_name = (target_user["username"] if target_user and target_user["username"] else reply.from_user.first_name) or "Игрок"
    uid_sender = user["user_id"]
    await update.message.reply_text(
        f'🙎‍♂️ {user_link(uid_sender, username)} {past_form} {user_link(target_uid, target_name)}',
        parse_mode=ParseMode.HTML
    )


# ── Daily bonus ───────────────────────────────────────────────────────────────

async def handle_bonus(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    vip = user.get("vip", 0)
    total_income = await get_total_income(uid)

    now_moscow = datetime.now(MOSCOW_TZ)
    today_str = now_moscow.strftime("%Y-%m-%d")

    # VIP4: can claim twice (every 12h), others once per day (reset 00:00 MSK)
    last_bonus = user.get("last_bonus")

# Следующее окно: 00:00 или 12:00 МСК
    now_hour = now_moscow.hour
    today_date = now_moscow.date()

    if vip >= 4:
        # Два окна: 00:00 и 12:00
        if now_hour < 12:
            current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=0)))
            next_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=12)))
        else:
            current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time().replace(hour=12)))
            next_window = MOSCOW_TZ.localize(datetime.combine(today_date + timedelta(days=1), datetime.min.time().replace(hour=0)))

        if last_bonus:
            last_dt = datetime.fromisoformat(last_bonus)
            if last_dt.tzinfo is None:
                last_dt = MOSCOW_TZ.localize(last_dt)
            if last_dt >= current_window:
                diff = next_window - now_moscow
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                await update.message.reply_text(f"⏳ Уже забирал! Следующий через: {h} ч. {m} мин.")
                return
    else:
        # Одно окно: 00:00
        current_window = MOSCOW_TZ.localize(datetime.combine(today_date, datetime.min.time()))
        next_window = MOSCOW_TZ.localize(datetime.combine(today_date + timedelta(days=1), datetime.min.time()))

        if last_bonus:
            last_dt = datetime.fromisoformat(last_bonus)
            if last_dt.tzinfo is None:
                last_dt = MOSCOW_TZ.localize(last_dt)
            if last_dt >= current_window:
                diff = next_window - now_moscow
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                await update.message.reply_text(f"⏳ Уже забирал! Следующий через: {h} ч. {m} мин.")
                return

    # Calculate bonus: 180-240% of total income
    multiplier = random.uniform(1.8, 2.4)
    bonus = int(total_income * multiplier)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
            (bonus, now_moscow.isoformat(), uid)
        )
        await db.commit()

    await update.message.reply_text(
        f"{user_link(uid, username)}, твой ежедневный бонус: {fmt_smart(bonus)} кр."
    , parse_mode=ParseMode.HTML)


# ── Top handler (message) ─────────────────────────────────────────────────────

async def handle_top(update: Update, user: dict, category: str = "rating"):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = await build_top_text(uid, category)
    kb = top_keyboard(category)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Main message handler ──────────────────────────────────────────────────────

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

        if parts[0].lower() == "добпромо" and len(parts) >= 4:
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
        bet_type = parts_g[1].lower()
        bet = parse_bet(parts_g[2], user["balance"])
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        num = random.randint(0, 36)
        red_nums = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        win = 0
        if bet_type.isdigit() and int(bet_type) == num:
            win = bet * 35
            desc = f"🎯 Число {num}! Выигрыш x35!"
        elif bet_type in ("красное", "red") and num in red_nums:
            win = bet * 2
            desc = f"🔴 Красное! Число {num}. x2"
        elif bet_type in ("чёрное", "black") and num not in red_nums and num != 0:
            win = bet * 2
            desc = f"⚫️ Чёрное! Число {num}. x2"
        elif bet_type in ("чётное", "even") and num % 2 == 0 and num != 0:
            win = bet * 2
            desc = f"✅ Чётное! Число {num}. x2"
        elif bet_type in ("нечётное", "odd") and num % 2 == 1:
            win = bet * 2
            desc = f"✅ Нечётное! Число {num}. x2"
        elif bet_type == "1-12" and 1 <= num <= 12:
            win = bet * 3
            desc = f"✅ 1-12! Число {num}. x3"
        elif bet_type == "13-24" and 13 <= num <= 24:
            win = bet * 3
            desc = f"✅ 13-24! Число {num}. x3"
        elif bet_type == "25-36" and 25 <= num <= 36:
            win = bet * 3
            desc = f"✅ 25-36! Число {num}. x3"
        else:
            desc = f"❌ Проигрыш. Выпало {num}."
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🎮 {user_link(uid, user['username'])}\n"
            f"🎡 Шарик: {num}\n"
            f"💸 Ставка: {fmt_smart(bet)} кр.\n"
            f"{desc}\n"
            f"📊 Итог: {sign}{fmt_smart(change)} кр.",
            parse_mode=ParseMode.HTML
        )
        return

    # Кубик
    if text.startswith("кубик"):
        parts_g = raw.split()
        if len(parts_g) < 3 or not parts_g[1].isdigit():
            await update.message.reply_text(f"Пример: <code>Кубик [число 1-6] [ставка]</code>", parse_mode=ParseMode.HTML)
            return
        guess = int(parts_g[1])
        bet = parse_bet(parts_g[2], user["balance"])
        if guess < 1 or guess > 6:
            await update.message.reply_text("Число от 1 до 6!", parse_mode=ParseMode.HTML)
            return
        if bet <= 0 or user["balance"] < bet:
            await update.message.reply_text(f"{user_link(uid, user['username'])}, недостаточно крышек!", parse_mode=ParseMode.HTML)
            return
        rolled = random.randint(1, 6)
        dice_emojis = {1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣"}
        if rolled == guess:
            win = bet * 5
            desc = f"🎯 Угадал! Выпало {dice_emojis[rolled]}. x5"
        else:
            win = 0
            desc = f"❌ Не угадал. Выпало {dice_emojis[rolled]}."
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        sign = "+" if change >= 0 else ""
        await update.message.reply_text(
            f"🎲 {user_link(uid, user['username'])}\n"
            f"💸 Ставка: {fmt_smart(bet)} кр. на {dice_emojis[guess]}\n"
            f"{desc}\n"
            f"📊 Итог: {sign}{fmt_smart(change)} кр.",
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
        sticker_msg = await update.message.reply_sticker("CAACAgIAAxkBAAIBd2cKW4k5tN3RAAGzAAFLUPGRAAFiXQACDgADwDZIE6ZaHBtV0XNHBQQ")
        await asyncio.sleep(2)
        pins = random.randint(0, 10)
        if pins == 10:
            mult, win = 3, bet * 3
            desc = f"🎳 СТРАЙК! Все 10 кеглей! x3"
        elif pins >= 7:
            mult, win = 1.5, int(bet * 1.5)
            desc = f"🎳 Отлично! {pins}/10 кеглей. x1.5"
        elif pins >= 4:
            mult, win = 1, bet
            desc = f"😐 {pins}/10 кеглей. x1 (возврат)"
        else:
            mult, win = 0, 0
            desc = f"❌ Промах. {pins}/10 кеглей. x0"
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
        sticker_msg = await update.message.reply_sticker("CAACAgIAAxkBAAIBd2cKW4k5tN3RAAGzAAFLUPGRAAFiXQACDgADwDZIE6ZaHBtV0XNHBQQ")
        await asyncio.sleep(2)
        roll = random.randint(1, 10)
        if roll >= 8:
            win, desc = bet * 2, f"🏀 Попал в кольцо! x2"
        elif roll >= 5:
            win, desc = int(bet * 1.2), f"🏀 Рикошет и попал! x1.2"
        else:
            win, desc = 0, f"❌ Промах мимо кольца! x0"
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
        sticker_msg = await update.message.reply_sticker("CAACAgIAAxkBAAIBd2cKW4k5tN3RAAGzAAFLUPGRAAFiXQACDgADwDZIE6ZaHBtV0XNHBQQ")
        await asyncio.sleep(2)
        roll = random.randint(1, 100)
        if roll <= 5:
            win, mult, desc = bet * 10, "x10", "меткость твоё второе имя! БУЛЛСАЙ! 🎯"
        elif roll <= 20:
            win, mult, desc = bet * 5, "x5", "отличный бросок! 🎯"
        elif roll <= 45:
            win, mult, desc = bet * 2, "x2", "попал! x2 🎯"
        elif roll <= 65:
            win, mult, desc = bet, "x1", "попал рядом с центром. x1 🤨"
        else:
            win, mult, desc = 0, "x0", "промахнулся! x0 😱"
        change = win - bet
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = balance - ? + ? WHERE user_id=?", (bet, win, uid))
            await db.commit()
        if change > 0:
            result_line = f"🎉 Выигрыш: {fmt_smart(win)} GPoint"
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

        cd_seconds = get_room_upgrade_cd(user.get("vip", 0), levels)
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
        use_bottles = context.user_data.get(f"room_{room_num}_bottles", False)
        result_data = await do_room_upgrade(uid, room_num, levels, use_bottles)
        if isinstance(result_data, tuple):
            result, fire = result_data
        else:
            result, fire = result_data, False
        if result:
            await query.answer(result[:200])
        else:
            await query.answer()
        if fire:
            try:
                chat_id = query.message.chat_id
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔥 {user_link(uid, (await get_user(uid))['username'])}, в бункере произошёл пожар!\n"
                         f"Напиши <code>Починить бункер</code> для починки.",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
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

async def cmd_balance_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_balance(update, user)


async def cmd_ref_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_ref(update, user)


async def cmd_bonus_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_bonus(update, user)


async def cmd_donation_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update):
        return
    uid = update.effective_user.id
    user = await get_user(uid)
    await handle_donate(update, user)


async def cmd_rooms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_rooms_list(update, context)

async def cmd_top_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_top(update, user, "rating")

async def cmd_cases_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_barrels_info(update, user)

async def cmd_rating_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_rating(update, user)

async def water_refill_job(context: ContextTypes.DEFAULT_TYPE):
    """Добавляет 1 воду каждые 10 минут, не превышая лимит."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT vip FROM users WHERE user_id=?", (uid,)) as cur2:
                row = await cur2.fetchone()
            if not row:
                continue
            vip = row[0]
            water_limit = get_vip_water_limit(vip)
            await db.execute(
                "UPDATE greenhouse SET water = MIN(water + 1, ?) WHERE user_id=?",
                (water_limit, uid)
            )
        await db.commit()

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

def ho_check_winner(board: list) -> int:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] != 0:
            return board[a]
    if all(x != 0 for x in board):
        return -1  # ничья
    return 0  # игра продолжается

def ho_keyboard(game_id: str, board: list) -> InlineKeyboardMarkup:
    symbols = {0: "⬜", 1: "❌", 2: "⭕️"}
    rows = []
    for i in range(3):
        row = []
        for j in range(3):
            idx = i*3+j
            row.append(InlineKeyboardButton(
                symbols[board[idx]],
                callback_data=f"ho_move_{game_id}_{idx}" if board[idx] == 0 else f"ho_no_{idx}"
            ))
        rows.append(row)
    return InlineKeyboardMarkup(rows)

async def handle_ho_start(update: Update, user: dict, bet: int):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    if user["balance"] < bet:
        await update.message.reply_text(f"{user_link(uid, username)}, недостаточно крышек!", parse_mode=ParseMode.HTML)
        return
    if bet <= 0:
        await update.message.reply_text("Ставка должна быть больше 0!", parse_mode=ParseMode.HTML)
        return
    game_id = str(uid)
    HO_GAMES[game_id] = {
        "p1": uid, "p2": None,
        "p1_name": username, "p2_name": "?",
        "bet": bet, "board": [0]*9, "turn": 1,
        "chat_id": update.message.chat_id,
        "active": False,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, uid))
        await db.commit()
    text = (
        f"❌⭕️ Крестики-нолики на {fmt_smart(bet)} GPoint\n\n"
        f"❌ {user_link(uid, username)}\n"
        f"⭕️ ?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Играть", callback_data=f"ho_join_{game_id}"),
         InlineKeyboardButton("🛑 Отменить", callback_data=f"ho_cancel_{game_id}")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

import time

def check_cooldown(uid: int) -> int:
    """Возвращает оставшиеся секунды КД, 0 если можно играть."""
    last = GAME_COOLDOWNS.get(uid, 0)
    diff = time.time() - last
    if diff < 3:
        return int(3 - diff) + 1
    return 0

def set_cooldown(uid: int):
    GAME_COOLDOWNS[uid] = time.time()

async def handle_fuel(update: Update, user: dict):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    total_income = await get_total_income(uid)
    fuel_per_hour = max(1, total_income // 5)
    max_fuel = fuel_per_hour * 12  # на 12 часов
    current_fuel = user.get("fuel", 0)

    text = (
        f"🙎‍♂️ {user_link(uid, username)}\n"
        f"🛢 Нефтехранилище\n\n"
        f"⛽️ Твой текущий запас бензина: {fmt_smart(int(current_fuel))}/{fmt_smart(max_fuel)} л.\n"
        f"🪫 Расход: {fmt_smart(fuel_per_hour)} л./час\n"
        f"💵 Цена за литр: 1 крышка"
    )
    need_full = max(0, max_fuel - current_fuel)
    need_hour = max(0, fuel_per_hour - current_fuel)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🛢 Купить до полного бака ({fmt_smart(int(need_full))} кр.)",
                              callback_data=f"fuel_full_{uid}")],
        [InlineKeyboardButton(f"⛽️ Купить на 1 час ({fmt_smart(fuel_per_hour)} кр.)",
                              callback_data=f"fuel_hour_{uid}")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def fuel_consume_job(context: ContextTypes.DEFAULT_TYPE):
    """Расходует бензин каждые 30 минут."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            all_users = await cur.fetchall()
        for (uid,) in all_users:
            async with db.execute("SELECT room_num, level FROM rooms WHERE user_id=?", (uid,)) as cur2:
                rooms = await cur2.fetchall()
            if not rooms:
                continue
            total_income = sum(get_current_income(r[0], r[1]) for r in rooms)
            fuel_per_half = max(1, total_income // 5) // 2
            await db.execute(
                "UPDATE users SET fuel = MAX(fuel - ?, 0) WHERE user_id=?",
                (fuel_per_half, uid)
            )
        await db.commit()


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
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())

