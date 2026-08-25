"""Общая бизнес-логика пользователей и профилей."""
# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from настройки import ADMIN_IDS
from вспомогательные.вспомогательные_функции import user_link
from вспомогательные.проверки import require_bunker
from вспомогательные.сообщения import build_bunker_text, build_top_text
from база_данных.база import get_user, create_bunker
from клавиатуры.общее import no_bunker_keyboard, back_keyboard
from клавиатуры.главное_меню import help_main_keyboard
from клавиатуры.бункер import top_keyboard


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

async def handle_top(update: Update, user: dict, category: str = "rating"):
    uid = user["user_id"]
    username = user["username"] or "Игрок"
    text = await build_top_text(uid, category)
    kb = top_keyboard(category)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Main message handler ──────────────────────────────────────────────────────

async def cmd_top_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_bunker(update): return
    user = await get_user(update.effective_user.id)
    await handle_top(update, user, "rating")
