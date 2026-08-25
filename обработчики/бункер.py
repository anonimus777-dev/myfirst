"""Логика бункера: бочки и расчёт ремонта."""

import random

from база_данных.бункер import BARREL_COLUMNS, get_barrels, ensure_barrels, remove_barrels

BARREL_NAMES = {
    1: "🛢 Обычную бочку",
    2: "🏺 Бронзовую бочку",
    3: "⚱️ Золотую бочку",
}


def get_vip_barrel_limit(vip: int) -> int:
    return {0: 1, 1: 5, 2: 10, 3: 25, 4: 50}.get(vip, 1)


def calculate_barrel_reward(barrel_num: int, quantity: int, total_income: int) -> dict[str, int]:
    reward = {"coins": 0, "rating": 0, "stimulators": 0, "weapons": 0}
    for _ in range(quantity):
        if barrel_num == 1:
            reward["coins"] += random.randint(1000, 4500)
            reward["rating"] += random.randint(1, 2) if random.random() < 0.20 else 0
            reward["stimulators"] += 1 if random.random() < 0.10 else 0
            reward["weapons"] += 1 if random.random() < 0.10 else 0
        elif barrel_num == 2:
            reward["coins"] += random.randint(5000, 30000)
            reward["rating"] += random.randint(1, 2) if random.random() < 0.25 else 0
            reward["stimulators"] += random.randint(1, 2) if random.random() < 0.10 else 0
            reward["weapons"] += random.randint(1, 2) if random.random() < 0.10 else 0
        elif barrel_num == 3:
            reward["coins"] += int(total_income * 3)
            reward["rating"] += random.randint(5, 50)
            reward["stimulators"] += random.randint(5, 20)
            reward["weapons"] += random.randint(5, 20)
        else:
            raise ValueError("Номер бочки должен быть от 1 до 3.")
    return reward


async def prepare_barrel_opening(user_id: int, barrel_num: int, quantity: int, vip: int) -> int:
    if barrel_num not in BARREL_COLUMNS:
        raise ValueError("Номер бочки должен быть от 1 до 3.")
    await ensure_barrels(user_id)
    barrels = await get_barrels(user_id)
    available = barrels[BARREL_COLUMNS[barrel_num]]
    if available <= 0:
        return 0
    quantity = min(max(1, quantity), get_vip_barrel_limit(vip), available)
    await remove_barrels(user_id, barrel_num, quantity)
    return quantity


def repair_cost(total_income: int) -> int:
    return int(total_income * 0.20)
