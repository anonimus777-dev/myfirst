# -*- coding: utf-8 -*-
"""
Модуль управления GitHub Codespaces через Telegram-бота.
Версия 3.0
"""

import asyncio
import html
import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes


TOKENS_FILE = "codespace_tokens.json"
WORK_HOURS = 59
KEEPALIVE_INTERVAL = 20
CHECK_INTERVAL = 60
IDLE_TIMEOUT = "4h"
POLLING_TIMEOUT = 120


def now_iso() -> str:
    return datetime.now().isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def escape_html(value: object) -> str:
    return html.escape(str(value))


def get_account_token(acc: Dict) -> Optional[str]:
    token = acc.get("token")
    if not token or not isinstance(token, str):
        return None
    return token.strip() or None


def get_account_name(acc: Dict, idx: int) -> str:
    name = acc.get("name")
    if name:
        return str(name)
    return f"Аккаунт {idx + 1}"


def load_data() -> Dict:
    if not os.path.exists(TOKENS_FILE):
        return {"accounts": [], "current_account": 0}
    try:
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Корень JSON должен быть объектом")
        if not isinstance(data.get("accounts"), list):
            raise ValueError("'accounts' должен быть списком")
        current = data.get("current_account", 0)
        if not isinstance(current, int):
            current = 0
        data["current_account"] = current
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"⚠️ Ошибка загрузки {TOKENS_FILE}: {e}")
        return {"accounts": [], "current_account": 0}


def save_data(data: Dict) -> None:
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        acc.pop("_status_cache", None)
        acc.pop("_last_check", None)
        acc.setdefault("active", False)
        acc.setdefault("started_at", None)
        acc.setdefault("codespace_name", None)
        acc.setdefault("used_seconds", 0)
        try:
            acc["used_seconds"] = max(0.0, float(acc["used_seconds"]))
        except (ValueError, TypeError):
            acc["used_seconds"] = 0.0
    data["accounts"] = accounts
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_accounts() -> List[Dict]:
    return load_data().get("accounts", [])


def save_accounts(accounts: List[Dict]) -> None:
    data = load_data()
    data["accounts"] = accounts
    save_data(data)


def get_current_index() -> int:
    data = load_data()
    accounts = data.get("accounts", [])
    idx = data.get("current_account", 0)
    if not accounts:
        return 0
    if not isinstance(idx, int):
        return 0
    if idx < 0 or idx >= len(accounts):
        return 0
    return idx


def set_current_index(idx: int) -> None:
    data = load_data()
    accounts = data.get("accounts", [])
    if accounts:
        if idx < 0 or idx >= len(accounts):
            idx = 0
    else:
        idx = 0
    data["current_account"] = idx
    save_data(data)


def run_gh_command(args: List[str], token: str, timeout: int = 60) -> Tuple[bool, str, str]:
    if not token:
        return False, "", "Пустой GitHub token"
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Команда gh превысила timeout"
    except FileNotFoundError:
        return False, "", "Команда 'gh' не найдена. Установи GitHub CLI."
    except Exception as e:
        return False, "", str(e)


def gh_codespace_create(repo: str, token: str) -> Optional[str]:
    if not repo:
        return None
    unique_id = uuid.uuid4().hex[:10]
    display_name = f"tg-manager-{unique_id}"
    success, stdout, stderr = run_gh_command(
        ["gh", "codespace", "create", "--repo", repo, "--display-name", display_name,
         "--idle-timeout", IDLE_TIMEOUT, "--machine", "basic"],
        token, timeout=300
    )
    if not success:
        print(f"❌ Codespace create error: {stderr[:500]}")
        return None
    print(f"✅ gh codespace create выполнен: {stdout[:300]}")
    for _ in range(12):
        success, list_stdout, list_stderr = run_gh_command(
            ["gh", "codespace", "list", "--json", "name,state,createdAt,displayName,repository", "--limit", "100"],
            token, timeout=30
        )
        if success:
            try:
                data = json.loads(list_stdout)
                if isinstance(data, list):
                    for cs in data:
                        if cs.get("displayName") == display_name:
                            name = cs.get("name")
                            if name:
                                return name
            except json.JSONDecodeError:
                pass
        time.sleep(2)
    print(f"❌ Не удалось найти созданный Codespace с display-name {display_name}")
    return None


def gh_codespace_start(name: str, token: str) -> bool:
    if not name:
        return False
    success, _, stderr = run_gh_command(
        ["gh", "codespace", "start", "--codespace", name],
        token, timeout=120
    )
    if not success:
        print(f"❌ Codespace start error {name}: {stderr[:300]}")
    return success


def gh_codespace_stop(name: str, token: str) -> bool:
    if not name:
        return False
    success, _, stderr = run_gh_command(
        ["gh", "codespace", "stop", "--codespace", name],
        token, timeout=60
    )
    if not success:
        print(f"❌ Codespace stop error {name}: {stderr[:300]}")
    return success


def gh_codespace_delete(name: str, token: str) -> bool:
    if not name:
        return False
    success, _, stderr = run_gh_command(
        ["gh", "codespace", "delete", "--codespace", name, "--force"],
        token, timeout=60
    )
    if not success:
        print(f"❌ Codespace delete error {name}: {stderr[:300]}")
    return success


def gh_codespace_list(token: str) -> List[Dict]:
    if not token:
        return []
    success, stdout, stderr = run_gh_command(
        ["gh", "codespace", "list", "--json", "name,state,createdAt,machineName,displayName,repository", "--limit", "100"],
        token, timeout=30
    )
    if not success:
        print(f"❌ Codespace list error: {stderr[:300]}")
        return []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка JSON при получении Codespaces: {e}")
    return []


def gh_codespace_status(name: str, token: str) -> Optional[str]:
    if not name or not token:
        return None
    codespaces = gh_codespace_list(token)
    for cs in codespaces:
        if cs.get("name") == name:
            return cs.get("state")
    return None


def gh_keepalive(cs_name: str, token: str) -> bool:
    if not cs_name or not token:
        return False
    success, _, stderr = run_gh_command(
        ["gh", "codespace", "ssh", "--codespace", cs_name, "--", "printf", "keepalive\\n"],
        token, timeout=30
    )
    if not success:
        print(f"⚠️ Keepalive error {cs_name}: {stderr[:200]}")
    return success


def gh_codespace_has_ssh(cs_name: str, token: str) -> bool:
    if not cs_name or not token:
        return False
    success, _, _ = run_gh_command(
        ["gh", "codespace", "ssh", "--codespace", cs_name, "--", "printf", "test\\n"],
        token, timeout=20
    )
    return success


def accumulate_runtime(acc: Dict) -> float:
    started_at = parse_iso(acc.get("started_at"))
    if not started_at:
        return 0.0
    elapsed = (datetime.now() - started_at).total_seconds()
    if elapsed <= 0:
        acc["started_at"] = None
        return 0.0
    try:
        used_seconds = float(acc.get("used_seconds", 0))
    except (ValueError, TypeError):
        used_seconds = 0.0
    acc["used_seconds"] = used_seconds + elapsed
    acc["started_at"] = None
    return elapsed


def get_used_seconds(acc: Dict) -> float:
    try:
        return max(0.0, float(acc.get("used_seconds", 0)))
    except (ValueError, TypeError):
        return 0.0


def get_account_status(acc: Dict, token: Optional[str]) -> Dict:
    used_seconds = get_used_seconds(acc)
    codespace_name = acc.get("codespace_name")
    started_at = acc.get("started_at")
    hours_used = used_seconds / 3600
    hours_left = max(0.0, WORK_HOURS - hours_used)

    if not token:
        return {
            "status": "no_token",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": codespace_name,
            "real_state": None
        }

    if not codespace_name:
        return {
            "status": "available",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": None,
            "real_state": None
        }

    real_status = gh_codespace_status(codespace_name, token)

    if real_status is None:
        accumulate_runtime(acc)
        acc["codespace_name"] = None
        acc["active"] = False
        used_seconds = get_used_seconds(acc)
        hours_used = used_seconds / 3600
        hours_left = max(0.0, WORK_HOURS - hours_used)
        return {
            "status": "available",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": None,
            "real_state": None
        }

    if real_status in ("Stopped", "Shutdown"):
        if started_at:
            accumulate_runtime(acc)
        used_seconds = get_used_seconds(acc)
        return {
            "status": "stopped",
            "used_hours": round(used_seconds / 3600, 1),
            "hours_left": round(max(0.0, WORK_HOURS - used_seconds / 3600), 1),
            "codespace_name": codespace_name,
            "real_state": real_status
        }

    if real_status in ("Starting", "Running"):
        if not started_at:
            acc["started_at"] = now_iso()
            started_at = acc["started_at"]
        start_time = parse_iso(started_at)
        if start_time:
            current_elapsed = max(0.0, (datetime.now() - start_time).total_seconds())
        else:
            current_elapsed = 0.0
        total_used = used_seconds + current_elapsed
        hours_used = total_used / 3600
        hours_left = max(0.0, WORK_HOURS - hours_used)
        return {
            "status": "running" if real_status == "Running" else "starting",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": codespace_name,
            "real_state": real_status
        }

    return {
        "status": "unknown",
        "used_hours": round(hours_used, 1),
        "hours_left": round(hours_left, 1),
        "codespace_name": codespace_name,
        "real_state": real_status
    }


def find_next_available_account(accounts: List[Dict]) -> int:
    if not accounts:
        return 0
    current_idx = get_current_index()
    n = len(accounts)
    for offset in range(1, n + 1):
        idx = (current_idx + offset) % n
        acc = accounts[idx]
        token = get_account_token(acc)
        if not token:
            continue
        status = get_account_status(acc, token)
        if status["hours_left"] > 1.0:
            return idx
    return current_idx


async def wait_for_running(cs_name: str, token: str, timeout: int = POLLING_TIMEOUT) -> bool:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        status = await asyncio.to_thread(gh_codespace_status, cs_name, token)
        print(f"⏳ Проверка {cs_name}: {status}")
        if status == "Running":
            return True
        if status in ("Stopped", "Shutdown", "Failed"):
            return False
        await asyncio.sleep(5)
    print(f"⏰ Timeout ожидания Codespace {cs_name}")
    return False


async def switch_to_account(accounts: List[Dict], target_idx: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, str]:
    if not accounts:
        return False, "❌ Нет аккаунтов."
    if target_idx < 0 or target_idx >= len(accounts):
        return False, "❌ Неверный индекс аккаунта."

    current_idx = get_current_index()
    target_acc = accounts[target_idx]
    target_name = get_account_name(target_acc, target_idx)
    target_token = get_account_token(target_acc)

    if not target_token:
        return False, f"❌ У {target_name} нет GitHub-токена."

    repo = target_acc.get("repo")
    if not repo:
        return False, f"❌ У {target_name} нет repo."

    cs_name = target_acc.get("codespace_name")
    cs_status = None
    if cs_name:
        cs_status = await asyncio.to_thread(gh_codespace_status, cs_name, target_token)

    if cs_name and cs_status in ("Stopped", "Shutdown"):
        print(f"⏳ Запускаем {cs_name}...")
        success = await asyncio.to_thread(gh_codespace_start, cs_name, target_token)
        if not success:
            return False, f"❌ Не удалось запустить {cs_name}"
        if not await wait_for_running(cs_name, target_token):
            return False, f"❌ {cs_name} не перешёл в Running."

    elif not cs_name or cs_status is None:
        print(f"⏳ Создаём Codespace для {target_name}...")
        cs_name = await asyncio.to_thread(gh_codespace_create, repo, target_token)
        if not cs_name:
            return False, f"❌ Не удалось определить созданный Codespace."
        if not await wait_for_running(cs_name, target_token):
            print(f"🗑 Удаляем не запустившийся Codespace {cs_name}")
            await asyncio.to_thread(gh_codespace_delete, cs_name, target_token)
            return False, f"❌ Codespace не запустился. Он удалён."

    elif cs_status == "Running":
        print(f"✅ {cs_name} уже работает.")
    else:
        return False, f"❌ Неизвестный статус {cs_name}: {cs_status}"

    target_acc["codespace_name"] = cs_name
    target_acc["active"] = True
    if not target_acc.get("started_at"):
        target_acc["started_at"] = now_iso()

    if current_idx != target_idx:
        old_acc = accounts[current_idx]
        old_cs_name = old_acc.get("codespace_name")
        old_token = get_account_token(old_acc)

        if old_acc.get("started_at"):
            accumulate_runtime(old_acc)

        if old_cs_name:
            tasks = context.bot_data.get("keepalive_tasks", {})
            task = tasks.pop(old_cs_name, None)
            if task:
                task.cancel()

        if old_cs_name and old_token:
            await asyncio.to_thread(gh_codespace_stop, old_cs_name, old_token)

        old_acc["active"] = False

    save_accounts(accounts)
    set_current_index(target_idx)

    await start_keepalive_for_account(cs_name, target_token, context)

    return True, f"✅ Переключено на {escape_html(target_name)}"


async def start_keepalive_for_account(cs_name: str, token: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not cs_name or not token:
        return

    tasks = context.bot_data.setdefault("keepalive_tasks", {})
    old_task = tasks.get(cs_name)
    if old_task and not old_task.done():
        old_task.cancel()

    has_ssh = await asyncio.to_thread(gh_codespace_has_ssh, cs_name, token)
    if not has_ssh:
        print(f"⚠️ Не удалось выполнить SSH-команду в {cs_name}. Keepalive не запущен.")
        return

    task = asyncio.create_task(keepalive_loop(cs_name, token))
    tasks[cs_name] = task
    print(f"✅ Keepalive запущен для {cs_name}")


async def keepalive_loop(cs_name: str, token: str) -> None:
    while True:
        try:
            await asyncio.sleep(KEEPALIVE_INTERVAL * 60)
            status = await asyncio.to_thread(gh_codespace_status, cs_name, token)
            if status != "Running":
                print(f"⏹ Keepalive завершён: {cs_name} ({status})")
                return
            success = await asyncio.to_thread(gh_keepalive, cs_name, token)
            if success:
                print(f"🔄 Keepalive {cs_name} {datetime.now().strftime('%H:%M:%S')}")
            else:
                print(f"⚠️ Keepalive не удался для {cs_name}")
        except asyncio.CancelledError:
            print(f"⏹ Keepalive отменён для {cs_name}")
            return
        except Exception as e:
            print(f"⚠️ Keepalive exception {cs_name}: {e}")


async def show_server(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    accounts = data.get("accounts", [])
    current_idx = get_current_index()

    if not accounts:
        await message.reply_text("📂 Нет настроенных аккаунтов.\n\nДобавь их через `codespace_tokens.json`.")
        return

    keyboard = []
    total_running = 0
    total_available = 0
    total_stopped = 0
    total_unknown = 0

    for idx, acc in enumerate(accounts):
        name = get_account_name(acc, idx)
        token = get_account_token(acc)
        status_data = get_account_status(acc, token)
        status = status_data["status"]
        hours_left = status_data["hours_left"]

        if status == "running":
            emoji = "🟢"
            total_running += 1
        elif status == "starting":
            emoji = "🟠"
        elif status == "available":
            emoji = "⚪"
            total_available += 1
        elif status == "stopped":
            emoji = "🟡"
            total_stopped += 1
        else:
            emoji = "🔴"
            total_unknown += 1

        current_mark = " 👈" if idx == current_idx else ""
        label = f"{emoji} {name} — {hours_left:.1f} ч.{current_mark}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cs_acc_{idx}")])

    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="cs_refresh"),
        InlineKeyboardButton("⏹ Остановить все", callback_data="cs_stop_all"),
    ])
    keyboard.append([
        InlineKeyboardButton("▶️ Запустить следующий", callback_data="cs_next"),
        InlineKeyboardButton("🔄 Переключить сейчас", callback_data="cs_switch_now"),
    ])
    keyboard.append([
        InlineKeyboardButton("📊 Использование", callback_data="cs_usage"),
        InlineKeyboardButton("➕ Добавить аккаунт", callback_data="cs_add"),
    ])

    current_acc = accounts[current_idx]
    current_name = get_account_name(current_acc, current_idx)
    current_token = get_account_token(current_acc)
    current_status = get_account_status(current_acc, current_token)

    text = (
        "<b>🖥 Управление Codespace</b>\n"
        "───────────────────\n"
        f"▶️ <b>Текущий:</b> {escape_html(current_name)}\n"
        f"⏱ Статус: {escape_html(current_status['status'])}\n"
        f"⌛️ Осталось: {current_status['hours_left']:.1f} ч.\n"
        "───────────────────\n"
        f"📊 <b>Всего:</b> {len(accounts)} акк.\n"
        f"🟢 Работает: {total_running}\n"
        f"🟡 Остановлен: {total_stopped}\n"
        f"⚪ Доступен: {total_available}\n"
    )
    if total_unknown:
        text += f"🔴 Ошибка: {total_unknown}\n"
    text += "───────────────────\nНажми на аккаунт для управления."

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def cmd_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        from настройки import ADMIN_IDS
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ У вас нет доступа.")
            return
    except ImportError:
        pass
    await show_server(update.message, context)


async def cs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cs_refresh":
        await query.message.edit_text("🔄 Обновляю...")
        await show_server(query.message, context)
        return

    accounts = load_accounts()
    if not accounts:
        await query.message.edit_text("📂 Нет аккаунтов.")
        return

    if data == "cs_stop_all":
        stopped = 0
        for acc in accounts:
            cs_name = acc.get("codespace_name")
            token = get_account_token(acc)
            if acc.get("started_at"):
                accumulate_runtime(acc)
            if cs_name:
                tasks = context.bot_data.get("keepalive_tasks", {})
                task = tasks.pop(cs_name, None)
                if task:
                    task.cancel()
            if cs_name and token:
                await asyncio.to_thread(gh_codespace_stop, cs_name, token)
                stopped += 1
            acc["active"] = False
        save_accounts(accounts)
        await query.message.edit_text(f"⏹ Остановлено {stopped} Codespace.")
        await show_server(query.message, context)
        return

    if data == "cs_next":
        current_idx = get_current_index()
        next_idx = find_next_available_account(accounts)
        if next_idx == current_idx:
            await query.message.edit_text("⚠️ Нет доступных аккаунтов.")
            return
        await query.message.edit_text(f"⏳ Переключаюсь на аккаунт {next_idx + 1}...")
        success, msg = await switch_to_account(accounts, next_idx, context)
        await query.message.edit_text(msg, parse_mode=ParseMode.HTML)
        await show_server(query.message, context)
        return

    if data == "cs_switch_now":
        if len(accounts) < 2:
            await query.message.edit_text("⚠️ Нужно минимум 2 аккаунта.")
            return
        current_idx = get_current_index()
        next_idx = (current_idx + 1) % len(accounts)
        await query.message.edit_text("⏳ Принудительное переключение...")
        success, msg = await switch_to_account(accounts, next_idx, context)
        await query.message.edit_text(msg, parse_mode=ParseMode.HTML)
        await show_server(query.message, context)
        return

    if data == "cs_add":
        await query.message.edit_text(
            "➕ <b>Как добавить аккаунт:</b>\n\n"
            "Отредактируй файл <code>codespace_tokens.json</code>:\n\n"
            "<pre>"
            "{\n"
            '  "accounts": [\n'
            "    {\n"
            '      "name": "acc1",\n'
            '      "token": "github_pat_xxx",\n'
            '      "repo": "owner/repo",\n'
            '      "active": false,\n'
            '      "started_at": null,\n'
            '      "codespace_name": null,\n'
            '      "used_seconds": 0\n'
            "    }\n"
            "  ],\n"
            '  "current_account": 0\n'
            "}"
            "</pre>\n\n"
            "После редактирования нажми <b>Обновить</b>.",
            parse_mode=ParseMode.HTML
        )
        return

    if data == "cs_usage":
        usage_text = "📊 <b>Использование Codespace</b>\n\n"
        for idx, acc in enumerate(accounts):
            name = get_account_name(acc, idx)
            token = get_account_token(acc)
            status = get_account_status(acc, token)
            usage_text += f"<b>{escape_html(name)}</b>: {escape_html(status['status'])} — {status['used_hours']:.1f} ч. использовано\n"
        await query.message.edit_text(usage_text, parse_mode=ParseMode.HTML)
        return

    if data.startswith("cs_acc_"):
        try:
            idx = int(data.split("_")[2])
        except (ValueError, IndexError):
            await query.message.edit_text("❌ Неверный индекс.")
            return

        if idx < 0 or idx >= len(accounts):
            await query.message.edit_text("❌ Аккаунт не найден.")
            return

        acc = accounts[idx]
        name = get_account_name(acc, idx)
        token = get_account_token(acc)
        status_data = get_account_status(acc, token)

        keyboard = []
        if status_data["status"] in ("available", "stopped"):
            keyboard.append([InlineKeyboardButton("▶️ Запустить", callback_data=f"cs_start_{idx}")])
        if status_data["status"] == "running":
            keyboard.append([InlineKeyboardButton("⏹ Остановить", callback_data=f"cs_stop_{idx}")])
            if idx != get_current_index():
                keyboard.append([InlineKeyboardButton("👈 Сделать текущим", callback_data=f"cs_make_current_{idx}")])
        keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"cs_del_{idx}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="cs_back")])

        text = (
            f"📂 <b>{escape_html(name)}</b>\n"
            "───────────────────\n"
            f"📊 Статус: {escape_html(status_data['status'])}\n"
            f"⏱ Использовано: {status_data['used_hours']:.1f} ч.\n"
            f"⌛️ Осталось: {status_data['hours_left']:.1f} ч.\n"
            f"💻 Codespace: {escape_html(status_data.get('codespace_name') or '-')}\n"
            "───────────────────\n"
            f"Текущий: {'✅ Да' if idx == get_current_index() else '❌ Нет'}"
        )

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        return

    if data.startswith("cs_start_"):
        try:
            idx = int(data.split("_")[2])
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        await query.message.edit_text("⏳ Запускаю...")
        success, msg = await switch_to_account(accounts, idx, context)
        await query.message.edit_text(msg, parse_mode=ParseMode.HTML)
        await show_server(query.message, context)
        return

    if data.startswith("cs_stop_"):
        try:
            idx = int(data.split("_")[2])
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]
        cs_name = acc.get("codespace_name")
        token = get_account_token(acc)

        if acc.get("started_at"):
            accumulate_runtime(acc)

        if cs_name:
            tasks = context.bot_data.get("keepalive_tasks", {})
            task = tasks.pop(cs_name, None)
            if task:
                task.cancel()

        if cs_name and token:
            await asyncio.to_thread(gh_codespace_stop, cs_name, token)

        acc["active"] = False
        save_accounts(accounts)

        if idx == get_current_index():
            next_idx = find_next_available_account(accounts)
            if next_idx != idx:
                await switch_to_account(accounts, next_idx, context)

        await query.message.edit_text(f"⏹ Аккаунт {idx + 1} остановлен.")
        await show_server(query.message, context)
        return

    if data.startswith("cs_make_current_"):
        try:
            idx = int(data.split("_")[3])
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]
        token = get_account_token(acc)

        if not token:
            await query.message.edit_text("❌ У аккаунта нет токена.")
            return

        status = get_account_status(acc, token)
        if status["status"] != "running":
            await query.message.edit_text("⚠️ Этот аккаунт не запущен.")
            return

        if idx == get_current_index():
            await query.message.edit_text("ℹ️ Этот аккаунт уже текущий.")
            return

        await query.message.edit_text("⏳ Переключаю...")
        success, msg = await switch_to_account(accounts, idx, context)
        await query.message.edit_text(msg, parse_mode=ParseMode.HTML)
        await show_server(query.message, context)
        return

    if data.startswith("cs_del_"):
        try:
            idx = int(data.split("_")[2])
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]
        cs_name = acc.get("codespace_name")
        token = get_account_token(acc)

        if acc.get("started_at"):
            accumulate_runtime(acc)

        if cs_name:
            tasks = context.bot_data.get("keepalive_tasks", {})
            task = tasks.pop(cs_name, None)
            if task:
                task.cancel()

        if cs_name and token:
            await asyncio.to_thread(gh_codespace_delete, cs_name, token)

        removed = accounts.pop(idx)
        current_idx = get_current_index()

        if not accounts:
            current_idx = 0
        elif idx == current_idx:
            if current_idx >= len(accounts):
                current_idx = 0
        elif idx < current_idx:
            current_idx -= 1

        data_save = load_data()
        data_save["accounts"] = accounts
        data_save["current_account"] = current_idx
        save_data(data_save)

        await query.message.edit_text(f"🗑 Аккаунт {escape_html(removed.get('name', ''))} удалён.")
        await show_server(query.message, context)
        return

    if data == "cs_back":
        await show_server(query.message, context)
        return


async def auto_rotate_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    accounts = load_accounts()
    if not accounts:
        return

    current_idx = get_current_index()
    if current_idx >= len(accounts):
        current_idx = 0
        set_current_index(0)

    acc = accounts[current_idx]
    token = get_account_token(acc)
    if not token:
        return

    status = get_account_status(acc, token)
    save_accounts(accounts)

    if status["hours_left"] <= 1.0:
        print(f"⏰ У аккаунта {current_idx + 1} осталось {status['hours_left']:.1f} ч.")
        next_idx = find_next_available_account(accounts)
        if next_idx == current_idx:
            print("⚠️ Другого доступного аккаунта нет.")
            return
        success, msg = await switch_to_account(accounts, next_idx, context)
        if success:
            print(f"✅ {msg}")
        else:
            print(f"❌ {msg}")


async def keepalive_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    accounts = load_accounts()
    if not accounts:
        return

    current_idx = get_current_index()
    if current_idx >= len(accounts):
        return

    acc = accounts[current_idx]
    if not acc.get("active"):
        return

    cs_name = acc.get("codespace_name")
    token = get_account_token(acc)

    if not cs_name or not token:
        return

    tasks = context.bot_data.setdefault("keepalive_tasks", {})
    task = tasks.get(cs_name)

    if task and not task.done():
        return

    await start_keepalive_for_account(cs_name, token, context)


def register_codespace_handlers(app) -> None:
    app.add_handler(CommandHandler("server", cmd_server))
    app.add_handler(CallbackQueryHandler(cs_callback, pattern=r"^cs_"))

    job_queue = app.job_queue
    if job_queue is None:
        print("⚠️ JobQueue недоступен. Для фоновых задач установи: pip install 'python-telegram-bot[job-queue]'")
        return

    job_queue.run_repeating(keepalive_task, interval=KEEPALIVE_INTERVAL * 60, first=60, name="codespace_keepalive")
    job_queue.run_repeating(auto_rotate_task, interval=CHECK_INTERVAL, first=30, name="codespace_auto_rotate")
    print("✅ Codespace Manager зарегистрирован")


def init_codespace_file() -> None:
    if os.path.exists(TOKENS_FILE):
        return

    example = {
        "accounts": [
            {
                "name": "acc1",
                "token": "github_pat_ваш_токен",
                "repo": "owner/repository",
                "active": False,
                "started_at": None,
                "codespace_name": None,
                "used_seconds": 0
            }
        ],
        "current_account": 0
    }

    try:
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2, ensure_ascii=False)
        print(f"📄 Создан файл {TOKENS_FILE}")
    except OSError as e:
        print(f"❌ Не удалось создать {TOKENS_FILE}: {e}")


init_codespace_file()
