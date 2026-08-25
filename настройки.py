"""Конфигурация приложения.

Никогда не добавляйте реальные токены в Git. Перед запуском задайте переменную
окружения BOT_TOKEN.
"""

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = os.environ.get("DB_PATH", "bunker.db")

if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана.")
