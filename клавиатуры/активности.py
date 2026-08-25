"""Меню активностей: бочки, теплица, шахта, сад, пустошь и гильдии."""
# -*- coding: utf-8 -*-
from telegram import Update
from telegram.constants import ParseMode
from настройки import RP_COMMANDS
from вспомогательные.вспомогательные_функции import user_link, safe_nick
from база_данных.база import get_user


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
