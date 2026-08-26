
# -*- coding: utf-8 -*-
"""
Модуль управления GitHub Codespaces через Telegram-бота.

Версия 3.0
- GH_TOKEN используется отдельно для каждого GitHub-аккаунта.
- Не используется глобальная авторизация gh.
- Codespace определяется надёжно через display-name + gh codespace list.
- Корректно считается накопленное время.
- Повторный запуск уже работающего Codespace не сбрасывает started_at.
- Keepalive выполняется внутри Codespace через gh codespace ssh.
- Старый Codespace останавливается только после успешного запуска нового.
- Защита от отсутствующего JobQueue.
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


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

TOKENS_FILE = "codespace_tokens.json"

# Лимит времени, который бот считает для каждого аккаунта.
WORK_HOURS = 59

# Keepalive каждые 20 минут.
KEEPALIVE_INTERVAL = 20

# Проверка состояния каждую минуту.
CHECK_INTERVAL = 60

# GitHub Codespaces допускает idle timeout от 5 до 240 минут.
IDLE_TIMEOUT = "4h"

# Максимальное время ожидания запуска Codespace.
POLLING_TIMEOUT = 120


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def now_iso() -> str:
    """Возвращает текущее локальное время в ISO-формате."""
    return datetime.now().isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Безопасно преобразует ISO-строку в datetime."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def escape_html(value: object) -> str:
    """Безопасно вставляет значение в Telegram HTML."""
    return html.escape(str(value))


def get_account_token(acc: Dict) -> Optional[str]:
    """
    Получает токен непосредственно из аккаунта.

    Это надёжнее, чем искать токен по имени аккаунта:
    два аккаунта могут иметь одинаковое name.
    """
    token = acc.get("token")

    if not token or not isinstance(token, str):
        return None

    return token.strip() or None


def get_account_name(acc: Dict, idx: int) -> str:
    """Возвращает отображаемое имя аккаунта."""
    name = acc.get("name")

    if name:
        return str(name)

    return f"Аккаунт {idx + 1}"


# ============================================================
# JSON / СОСТОЯНИЕ
# ============================================================

def load_data() -> Dict:
    """Загружает состояние из codespace_tokens.json."""

    if not os.path.exists(TOKENS_FILE):
        return {
            "accounts": [],
            "current_account": 0
        }

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

        return {
            "accounts": [],
            "current_account": 0
        }


def save_data(data: Dict) -> None:
    """Сохраняет состояние в JSON."""

    accounts = data.get("accounts", [])

    if not isinstance(accounts, list):
        accounts = []

    for acc in accounts:
        if not isinstance(acc, dict):
            continue

        # Временные поля, если они когда-либо появятся.
        acc.pop("_status_cache", None)
        acc.pop("_last_check", None)

        # Гарантируем наличие основных полей.
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
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def load_accounts() -> List[Dict]:
    """Загружает список аккаунтов."""

    return load_data().get("accounts", [])


def save_accounts(accounts: List[Dict]) -> None:
    """Сохраняет список аккаунтов, не изменяя current_account."""

    data = load_data()
    data["accounts"] = accounts
    save_data(data)


def get_current_index() -> int:
    """Возвращает корректный индекс текущего аккаунта."""

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
    """Устанавливает текущий аккаунт."""

    data = load_data()
    accounts = data.get("accounts", [])

    if accounts:
        if idx < 0 or idx >= len(accounts):
            idx = 0
    else:
        idx = 0

    data["current_account"] = idx
    save_data(data)


# ============================================================
# GITHUB CLI
# ============================================================

def run_gh_command(
    args: List[str],
    token: str,
    timeout: int = 60
) -> Tuple[bool, str, str]:
    """
    Выполняет gh-команду с конкретным GitHub-токеном.

    Токен передаётся через GH_TOKEN.
    shell=True НЕ используется.
    """

    if not token:
        return False, "", "Пустой GitHub token"

    env = os.environ.copy()
    env["GH_TOKEN"] = token

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        return (
            result.returncode == 0,
            result.stdout.strip(),
            result.stderr.strip()
        )

    except subprocess.TimeoutExpired:
        return False, "", "Команда gh превысила timeout"

    except FileNotFoundError:
        return False, "", (
            "Команда 'gh' не найдена. "
            "Установи GitHub CLI."
        )

    except Exception as e:
        return False, "", str(e)


# ============================================================
# CODESPACE CREATE
# ============================================================

def gh_codespace_create(
    repo: str,
    token: str
) -> Optional[str]:
    """
    Создаёт Codespace и надёжно определяет его name.

    gh codespace create не используем с --json.
    Вместо этого создаём уникальный display-name,
    затем ищем Codespace через gh codespace list.
    """

    if not repo:
        return None

    unique_id = uuid.uuid4().hex[:10]

    display_name = f"tg-manager-{unique_id}"

    success, stdout, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "create",
            "--repo",
            repo,
            "--display-name",
            display_name,
            "--idle-timeout",
            IDLE_TIMEOUT,
            "--machine",
            "basic"
        ],
        token,
        timeout=300
    )

    if not success:
        print(
            f"❌ Codespace create error: "
            f"{stderr[:500]}"
        )
        return None

    print(
        f"✅ gh codespace create выполнен: "
        f"{stdout[:300]}"
    )

    # После создания некоторое время Codespace может
    # ещё не появляться в list.
    for _ in range(12):
        success, list_stdout, list_stderr = run_gh_command(
            [
                "gh",
                "codespace",
                "list",
                "--json",
                "name,state,createdAt,displayName,repository",
                "--limit",
                "100"
            ],
            token,
            timeout=30
        )

        if success:
            try:
                data = json.loads(list_stdout)

                if isinstance(data, list):
                    # Ищем именно наш display-name.
                    for cs in data:
                        if cs.get("displayName") == display_name:
                            name = cs.get("name")

                            if name:
                                return name

            except json.JSONDecodeError:
                pass

        time.sleep(2)

    print(
        f"❌ Не удалось найти созданный Codespace "
        f"с display-name {display_name}"
    )

    return None


# ============================================================
# CODESPACE START / STOP / DELETE
# ============================================================

def gh_codespace_start(
    name: str,
    token: str
) -> bool:
    """Запускает существующий Codespace."""

    if not name:
        return False

    success, _, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "start",
            "--codespace",
            name
        ],
        token,
        timeout=120
    )

    if not success:
        print(
            f"❌ Codespace start error "
            f"{name}: {stderr[:300]}"
        )

    return success


def gh_codespace_stop(
    name: str,
    token: str
) -> bool:
    """Останавливает Codespace."""

    if not name:
        return False

    success, _, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "stop",
            "--codespace",
            name
        ],
        token,
        timeout=60
    )

    if not success:
        print(
            f"❌ Codespace stop error "
            f"{name}: {stderr[:300]}"
        )

    return success


def gh_codespace_delete(
    name: str,
    token: str
) -> bool:
    """Удаляет Codespace."""

    if not name:
        return False

    success, _, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "delete",
            "--codespace",
            name,
            "--force"
        ],
        token,
        timeout=60
    )

    if not success:
        print(
            f"❌ Codespace delete error "
            f"{name}: {stderr[:300]}"
        )

    return success


# ============================================================
# CODESPACE LIST / STATUS
# ============================================================

def gh_codespace_list(
    token: str
) -> List[Dict]:
    """Получает список Codespaces текущего GitHub-аккаунта."""

    if not token:
        return []

    success, stdout, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "list",
            "--json",
            "name,state,createdAt,machineName,displayName,repository",
            "--limit",
            "100"
        ],
        token,
        timeout=30
    )

    if not success:
        print(
            f"❌ Codespace list error: "
            f"{stderr[:300]}"
        )
        return []

    try:
        data = json.loads(stdout)

        if isinstance(data, list):
            return data

    except json.JSONDecodeError as e:
        print(
            f"❌ Ошибка JSON при получении Codespaces: {e}"
        )

    return []


def gh_codespace_status(
    name: str,
    token: str
) -> Optional[str]:
    """
    Возвращает реальный state Codespace.

    Например:
    Running
    Starting
    Stopped
    Shutdown
    """
    if not name or not token:
        return None

    codespaces = gh_codespace_list(token)

    for cs in codespaces:
        if cs.get("name") == name:
            return cs.get("state")

    return None


# ============================================================
# KEEPALIVE
# ============================================================

def gh_keepalive(
    cs_name: str,
    token: str
) -> bool:
    """
    Выполняет команду внутри Codespace.

    gh codespace ssh не требует отдельного SSH-сервера
    внутри devcontainer.
    """

    if not cs_name or not token:
        return False

    success, _, stderr = run_gh_command(
        [
            "gh",
            "codespace",
            "ssh",
            "--codespace",
            cs_name,
            "--",
            "printf",
            "keepalive\\n"
        ],
        token,
        timeout=30
    )

    if not success:
        print(
            f"⚠️ Keepalive error {cs_name}: "
            f"{stderr[:200]}"
        )

    return success


def gh_codespace_has_ssh(
    cs_name: str,
    token: str
) -> bool:
    """
    Проверяет, может ли gh codespace ssh выполнить команду.
    """

    if not cs_name or not token:
        return False

    success, _, _ = run_gh_command(
        [
            "gh",
            "codespace",
            "ssh",
            "--codespace",
            cs_name,
            "--",
            "printf",
            "test\\n"
        ],
        token,
        timeout=20
    )

    return success


# ============================================================
# УЧЁТ ВРЕМЕНИ
# ============================================================

def accumulate_runtime(acc: Dict) -> float:
    """
    Добавляет текущее время работы Codespace в used_seconds.

    ВАЖНО:
    после вызова started_at сбрасывается.
    Поэтому один и тот же интервал не будет посчитан повторно.
    """

    started_at = parse_iso(acc.get("started_at"))

    if not started_at:
        return 0.0

    elapsed = (
        datetime.now() - started_at
    ).total_seconds()

    if elapsed <= 0:
        acc["started_at"] = None
        return 0.0

    try:
        used_seconds = float(
            acc.get("used_seconds", 0)
        )
    except (ValueError, TypeError):
        used_seconds = 0.0

    acc["used_seconds"] = used_seconds + elapsed
    acc["started_at"] = None

    return elapsed


def get_used_seconds(acc: Dict) -> float:
    """Возвращает уже накопленное время."""

    try:
        return max(
            0.0,
            float(acc.get("used_seconds", 0))
        )
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# СТАТУС АККАУНТА
# ============================================================

def get_account_status(
    acc: Dict,
    token: Optional[str]
) -> Dict:
    """
    Возвращает реальный статус аккаунта.

    Эта функция НЕ должна сбрасывать started_at,
    если Codespace продолжает работать.
    """

    used_seconds = get_used_seconds(acc)
    codespace_name = acc.get("codespace_name")
    started_at = acc.get("started_at")

    hours_used = used_seconds / 3600
    hours_left = max(
        0.0,
        WORK_HOURS - hours_used
    )

    # Нет токена.
    if not token:
        return {
            "status": "no_token",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": codespace_name,
            "real_state": None
        }

    # Нет Codespace.
    if not codespace_name:
        return {
            "status": "available",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": None,
            "real_state": None
        }

    real_status = gh_codespace_status(
        codespace_name,
        token
    )

    # Codespace удалён или не найден.
    if real_status is None:
        # Если он был запущен, фиксируем последнее время.
        accumulate_runtime(acc)

        acc["codespace_name"] = None
        acc["active"] = False

        used_seconds = get_used_seconds(acc)
        hours_used = used_seconds / 3600
        hours_left = max(
            0.0,
            WORK_HOURS - hours_used
        )

        return {
            "status": "available",
            "used_hours": round(hours_used, 1),
            "hours_left": round(hours_left, 1),
            "codespace_name": None,
            "real_state": None
        }

    # Codespace остановлен.
    if real_status in ("Stopped", "Shutdown"):
        if started_at:
            accumulate_runtime(acc)

        used_seconds = get_used_seconds(acc)

        return {
            "status": "stopped",
            "used_hours": round(
                used_seconds / 3600,
                1
            ),
            "hours_left": round(
                max(
                    0.0,
                    WORK_HOURS -
                    used_seconds / 3600
                ),
                1
            ),
            "codespace_name": codespace_name,
            "real_state": real_status
        }

    # Codespace запускается или работает.
    if real_status in ("Starting", "Running"):
        # Если started_at отсутствует, начинаем новый
        # интервал только сейчас.
        if not started_at:
            acc["started_at"] = now_iso()
            started_at = acc["started_at"]

        start_time = parse_iso(started_at)

        if start_time:
            current_elapsed = max(
                0.0,
                (
                    datetime.now() - start_time
                ).total_seconds()
            )
        else:
            current_elapsed = 0.0

        total_used = used_seconds + current_elapsed
        hours_used = total_used / 3600
        hours_left = max(
            0.0,
            WORK_HOURS - hours_used
        )

        return {
            "status": (
                "running"
                if real_status == "Running"
                else "starting"
            ),
            "used_hours": round(
                hours_used,
                1
            ),
            "hours_left": round(
                hours_left,
                1
            ),
            "codespace_name": codespace_name,
            "real_state": real_status
        }

    return {
        "status": "unknown",
        "used_hours": round(
            hours_used,
            1
        ),
        "hours_left": round(
            hours_left,
            1
        ),
        "codespace_name": codespace_name,
        "real_state": real_status
    }


# ============================================================
# ПОИСК СЛЕДУЮЩЕГО АККАУНТА
# ============================================================

def find_next_available_account(
    accounts: List[Dict]
) -> int:
    """
    Ищет следующий аккаунт, у которого осталось > 1 часа.

    Токен берётся напрямую из account["token"].
    """

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

        status = get_account_status(
            acc,
            token
        )

        if status["hours_left"] > 1.0:
            return idx

    return current_idx


# ============================================================
# ОЖИДАНИЕ RUNNING
# ============================================================

async def wait_for_running(
    cs_name: str,
    token: str,
    timeout: int = POLLING_TIMEOUT
) -> bool:
    """Ждёт перехода Codespace в Running."""

    started = time.monotonic()

    while time.monotonic() - started < timeout:

        status = await asyncio.to_thread(
            gh_codespace_status,
            cs_name,
            token
        )

        print(
            f"⏳ Проверка {cs_name}: "
            f"{status}"
        )

        if status == "Running":
            return True

        if status in (
            "Stopped",
            "Shutdown",
            "Failed"
        ):
            return False

        await asyncio.sleep(5)

    print(
        f"⏰ Timeout ожидания Codespace "
        f"{cs_name}"
    )

    return False


# ============================================================
# ПЕРЕКЛЮЧЕНИЕ АККАУНТА
# ============================================================

async def switch_to_account(
    accounts: List[Dict],
    target_idx: int,
    context: ContextTypes.DEFAULT_TYPE
) -> Tuple[bool, str]:
    """
    Переключается на target_idx.

    Алгоритм:

    1. Проверяем целевой аккаунт.
    2. Находим существующий Codespace или создаём новый.
    3. Ждём Running.
    4. Только после успешного запуска останавливаем старый.
    5. Сохраняем время старого.
    6. Запускаем keepalive нового.
    """

    if not accounts:
        return False, "❌ Нет аккаунтов."

    if target_idx < 0 or target_idx >= len(accounts):
        return False, "❌ Неверный индекс аккаунта."

    current_idx = get_current_index()

    target_acc = accounts[target_idx]
    target_name = get_account_name(
        target_acc,
        target_idx
    )

    target_token = get_account_token(
        target_acc
    )

    if not target_token:
        return False, (
            f"❌ У {target_name} нет GitHub-токена."
        )

    repo = target_acc.get("repo")

    if not repo:
        return False, (
            f"❌ У {target_name} нет repo."
        )

    # --------------------------------------------------------
    # 1. Получаем существующий Codespace.
    # --------------------------------------------------------

    cs_name = target_acc.get(
        "codespace_name"
    )

    cs_status = None

    if cs_name:
        cs_status = await asyncio.to_thread(
            gh_codespace_status,
            cs_name,
            target_token
        )

    # --------------------------------------------------------
    # 2. Если Codespace существует и остановлен.
    # --------------------------------------------------------

    if cs_name and cs_status in (
        "Stopped",
        "Shutdown"
    ):

        print(
            f"⏳ Запускаем {cs_name}..."
        )

        success = await asyncio.to_thread(
            gh_codespace_start,
            cs_name,
            target_token
        )

        if not success:
            return False, (
                f"❌ Не удалось запустить "
                f"{cs_name}"
            )

        if not await wait_for_running(
            cs_name,
            target_token
        ):
            return False, (
                f"❌ {cs_name} "
                f"не перешёл в Running."
            )

    # --------------------------------------------------------
    # 3. Codespace отсутствует.
    # --------------------------------------------------------

    elif not cs_name or cs_status is None:

        print(
            f"⏳ Создаём Codespace "
            f"для {target_name}..."
        )

        cs_name = await asyncio.to_thread(
            gh_codespace_create,
            repo,
            target_token
        )

        if not cs_name:
            return False, (
                f"❌ Не удалось определить "
                f"созданный Codespace."
            )

        if not await wait_for_running(
            cs_name,
            target_token
        ):
            print(
                f"🗑 Удаляем не запустившийся "
                f"Codespace {cs_name}"
            )

            await asyncio.to_thread(
                gh_codespace_delete,
                cs_name,
                target_token
            )

            return False, (
                f"❌ Codespace не запустился. "
                f"Он удалён."
            )

    # --------------------------------------------------------
    # 4. Если он уже Running.
    # --------------------------------------------------------

    elif cs_status == "Running":

        print(
            f"✅ {cs_name} уже работает."
        )

    # --------------------------------------------------------
    # 5. Неизвестный статус.
    # --------------------------------------------------------

    else:
        return False, (
            f"❌ Неизвестный статус "
            f"{cs_name}: {cs_status}"
        )

    # --------------------------------------------------------
    # 6. Запоминаем Codespace.
    #
    # ВАЖНО:
    # если он уже работал, started_at НЕ сбрасываем.
    # --------------------------------------------------------

    target_acc["codespace_name"] = cs_name
    target_acc["active"] = True

    if not target_acc.get("started_at"):
        target_acc["started_at"] = now_iso()

    # --------------------------------------------------------
    # 7. Останавливаем старый аккаунт.
    # --------------------------------------------------------

    if current_idx != target_idx:

        old_acc = accounts[current_idx]

        old_cs_name = old_acc.get(
            "codespace_name"
        )

        old_token = get_account_token(
            old_acc
        )

        # Сначала фиксируем время.
        if old_acc.get("started_at"):
            accumulate_runtime(old_acc)

        # Останавливаем keepalive.
        if old_cs_name:
            tasks = context.bot_data.get(
                "keepalive_tasks",
                {}
            )

            task = tasks.pop(
                old_cs_name,
                None
            )

            if task:
                task.cancel()

        # Останавливаем Codespace.
        if old_cs_name and old_token:
            await asyncio.to_thread(
                gh_codespace_stop,
                old_cs_name,
                old_token
            )

        old_acc["active"] = False

    # --------------------------------------------------------
    # 8. Сохраняем состояние.
    # --------------------------------------------------------

    save_accounts(accounts)
    set_current_index(target_idx)

    # --------------------------------------------------------
    # 9. Запускаем keepalive.
    # --------------------------------------------------------

    await start_keepalive_for_account(
        cs_name,
        target_token,
        context
    )

    return True, (
        f"✅ Переключено на "
        f"{escape_html(target_name)}"
    )


# ============================================================
# KEEPALIVE TASK
# ============================================================

async def start_keepalive_for_account(
    cs_name: str,
    token: str,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Запускает отдельную asyncio-задачу keepalive."""

    if not cs_name or not token:
        return

    tasks = context.bot_data.setdefault(
        "keepalive_tasks",
        {}
    )

    old_task = tasks.get(cs_name)

    if old_task:
        if not old_task.done():
            old_task.cancel()

    # Проверяем SSH/доступ.
    has_ssh = await asyncio.to_thread(
        gh_codespace_has_ssh,
        cs_name,
        token
    )

    if not has_ssh:
        print(
            f"⚠️ Не удалось выполнить "
            f"SSH-команду в {cs_name}. "
            f"Keepalive не запущен."
        )
        return

    task = asyncio.create_task(
        keepalive_loop(
            cs_name,
            token
        )
    )

    tasks[cs_name] = task

    print(
        f"✅ Keepalive запущен "
        f"для {cs_name}"
    )


async def keepalive_loop(
    cs_name: str,
    token: str
) -> None:
    """
    Выполняет keepalive каждые KEEPALIVE_INTERVAL минут.
    """

    while True:

        try:
            await asyncio.sleep(
                KEEPALIVE_INTERVAL * 60
            )

            status = await asyncio.to_thread(
                gh_codespace_status,
                cs_name,
                token
            )

            if status != "Running":
                print(
                    f"⏹ Keepalive завершён: "
                    f"{cs_name} "
                    f"({status})"
                )
                return

            success = await asyncio.to_thread(
                gh_keepalive,
                cs_name,
                token
            )

            if success:
                print(
                    f"🔄 Keepalive "
                    f"{cs_name} "
                    f"{datetime.now().strftime('%H:%M:%S')}"
                )
            else:
                print(
                    f"⚠️ Keepalive не удался "
                    f"для {cs_name}"
                )

        except asyncio.CancelledError:
            print(
                f"⏹ Keepalive отменён "
                f"для {cs_name}"
            )
            return

        except Exception as e:
            print(
                f"⚠️ Keepalive exception "
                f"{cs_name}: {e}"
            )


# ============================================================
# TELEGRAM UI
# ============================================================

async def show_server(
    message,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показывает панель управления."""

    data = load_data()

    accounts = data.get(
        "accounts",
        []
    )

    current_idx = get_current_index()

    if not accounts:
        await message.reply_text(
            "📂 Нет настроенных аккаунтов.\n\n"
            "Добавь их через "
            "`codespace_tokens.json`."
        )
        return

    keyboard = []

    total_running = 0
    total_available = 0
    total_stopped = 0
    total_unknown = 0

    for idx, acc in enumerate(accounts):

        name = get_account_name(
            acc,
            idx
        )

        token = get_account_token(
            acc
        )

        status_data = get_account_status(
            acc,
            token
        )

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

        current_mark = (
            " 👈"
            if idx == current_idx
            else ""
        )

        label = (
            f"{emoji} {name} — "
            f"{hours_left:.1f} ч."
            f"{current_mark}"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"cs_acc_{idx}"
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔄 Обновить",
                callback_data="cs_refresh"
            ),
            InlineKeyboardButton(
                "⏹ Остановить все",
                callback_data="cs_stop_all"
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "▶️ Запустить следующий",
                callback_data="cs_next"
            ),
            InlineKeyboardButton(
                "🔄 Переключить сейчас",
                callback_data="cs_switch_now"
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "📊 Использование",
                callback_data="cs_usage"
            ),
            InlineKeyboardButton(
                "➕ Добавить аккаунт",
                callback_data="cs_add"
            )
        ]
    )

    current_acc = accounts[current_idx]

    current_name = get_account_name(
        current_acc,
        current_idx
    )

    current_token = get_account_token(
        current_acc
    )

    current_status = get_account_status(
        current_acc,
        current_token
    )

    text = (
        "<b>🖥 Управление Codespace</b>\n"
        "───────────────────\n"
        f"▶️ <b>Текущий:</b> "
        f"{escape_html(current_name)}\n"
        f"⏱ Статус: "
        f"{escape_html(current_status['status'])}\n"
        f"⌛️ Осталось: "
        f"{current_status['hours_left']:.1f} ч.\n"
        "───────────────────\n"
        f"📊 <b>Всего:</b> "
        f"{len(accounts)} акк.\n"
        f"🟢 Работает: "
        f"{total_running}\n"
        f"🟡 Остановлен: "
        f"{total_stopped}\n"
        f"⚪ Доступен: "
        f"{total_available}\n"
    )

    if total_unknown:
        text += (
            f"🔴 Ошибка: "
            f"{total_unknown}\n"
        )

    text += (
        "───────────────────\n"
        "Нажми на аккаунт для управления."
    )

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode=ParseMode.HTML
    )


# ============================================================
# /server
# ============================================================

async def cmd_server(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Команда /server."""

    user_id = update.effective_user.id

    try:
        from настройки import ADMIN_IDS

        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "⛔ У вас нет доступа."
            )
            return

    except ImportError:
        # Если настройки.py отсутствует,
        # доступ не блокируем.
        pass

    await show_server(
        update.message,
        context
    )


# ============================================================
# CALLBACK
# ============================================================

async def cs_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик inline-кнопок."""

    query = update.callback_query

    await query.answer()

    data = query.data

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    if data == "cs_refresh":

        await query.message.edit_text(
            "🔄 Обновляю..."
        )

        await show_server(
            query.message,
            context
        )

        return

    accounts = load_accounts()

    if not accounts:
        await query.message.edit_text(
            "📂 Нет аккаунтов."
        )
        return

    # --------------------------------------------------------
    # STOP ALL
    # --------------------------------------------------------

    if data == "cs_stop_all":

        stopped = 0

        for acc in accounts:

            cs_name = acc.get(
                "codespace_name"
            )

            token = get_account_token(
                acc
            )

            # Сначала фиксируем время.
            if acc.get("started_at"):
                accumulate_runtime(acc)

            # Отменяем keepalive.
            if cs_name:

                tasks = context.bot_data.get(
                    "keepalive_tasks",
                    {}
                )

                task = tasks.pop(
                    cs_name,
                    None
                )

                if task:
                    task.cancel()

            # Останавливаем Codespace.
            if cs_name and token:

                await asyncio.to_thread(
                    gh_codespace_stop,
                    cs_name,
                    token
                )

                stopped += 1

            acc["active"] = False

        save_accounts(accounts)

        await query.message.edit_text(
            f"⏹ Остановлено "
            f"{stopped} Codespace."
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # NEXT
    # --------------------------------------------------------

    if data == "cs_next":

        current_idx = get_current_index()

        next_idx = find_next_available_account(
            accounts
        )

        if next_idx == current_idx:

            await query.message.edit_text(
                "⚠️ Нет доступных аккаунтов."
            )

            return

        await query.message.edit_text(
            f"⏳ Переключаюсь "
            f"на аккаунт {next_idx + 1}..."
        )

        success, msg = await switch_to_account(
            accounts,
            next_idx,
            context
        )

        await query.message.edit_text(
            msg,
            parse_mode=ParseMode.HTML
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # SWITCH NOW
    # --------------------------------------------------------

    if data == "cs_switch_now":

        if len(accounts) < 2:

            await query.message.edit_text(
                "⚠️ Нужно минимум 2 аккаунта."
            )

            return

        current_idx = get_current_index()

        next_idx = (
            current_idx + 1
        ) % len(accounts)

        await query.message.edit_text(
            "⏳ Принудительное переключение..."
        )

        success, msg = await switch_to_account(
            accounts,
            next_idx,
            context
        )

        await query.message.edit_text(
            msg,
            parse_mode=ParseMode.HTML
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    if data == "cs_add":

        await query.message.edit_text(
            "➕ <b>Как добавить аккаунт:</b>\n\n"
            "Отредактируй файл "
            "<code>codespace_tokens.json</code>:\n\n"
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
            "После редактирования нажми "
            "<b>Обновить</b>.",
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # USAGE
    # --------------------------------------------------------

    if data == "cs_usage":

        usage_text = (
            "📊 <b>Использование Codespace</b>\n\n"
        )

        for idx, acc in enumerate(accounts):

            name = get_account_name(
                acc,
                idx
            )

            token = get_account_token(
                acc
            )

            status = get_account_status(
                acc,
                token
            )

            usage_text += (
                f"<b>{escape_html(name)}</b>: "
                f"{escape_html(status['status'])} — "
                f"{status['used_hours']:.1f} ч. "
                f"использовано\n"
            )

        await query.message.edit_text(
            usage_text,
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    if data.startswith("cs_acc_"):

        try:
            idx = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):
            await query.message.edit_text(
                "❌ Неверный индекс."
            )
            return

        if idx < 0 or idx >= len(accounts):

            await query.message.edit_text(
                "❌ Аккаунт не найден."
            )
            return

        acc = accounts[idx]

        name = get_account_name(
            acc,
            idx
        )

        token = get_account_token(
            acc
        )

        status_data = get_account_status(
            acc,
            token
        )

        keyboard = []

        if status_data["status"] in (
            "available",
            "stopped"
        ):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "▶️ Запустить",
                        callback_data=f"cs_start_{idx}"
                    )
                ]
            )

        if status_data["status"] == "running":

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⏹ Остановить",
                        callback_data=f"cs_stop_{idx}"
                    )
                ]
            )

            if idx != get_current_index():

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "👈 Сделать текущим",
                            callback_data=(
                                f"cs_make_current_{idx}"
                            )
                        )
                    ]
                )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑 Удалить",
                    callback_data=f"cs_del_{idx}"
                )
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "◀️ Назад",
                    callback_data="cs_back"
                )
            ]
        )

        text = (
            f"📂 <b>{escape_html(name)}</b>\n"
            "───────────────────\n"
            f"📊 Статус: "
            f"{escape_html(status_data['status'])}\n"
            f"⏱ Использовано: "
            f"{status_data['used_hours']:.1f} ч.\n"
            f"⌛️ Осталось: "
            f"{status_data['hours_left']:.1f} ч.\n"
            f"💻 Codespace: "
            f"{escape_html(status_data.get('codespace_name') or '-')}\n"
            "───────────────────\n"
            f"Текущий: "
            f"{'✅ Да' if idx == get_current_index() else '❌ Нет'}"
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if data.startswith("cs_start_"):

        try:
            idx = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        await query.message.edit_text(
            "⏳ Запускаю..."
        )

        success, msg = await switch_to_account(
            accounts,
            idx,
            context
        )

        await query.message.edit_text(
            msg,
            parse_mode=ParseMode.HTML
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    if data.startswith("cs_stop_"):

        try:
            idx = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]

        cs_name = acc.get(
            "codespace_name"
        )

        token = get_account_token(
            acc
        )

        # Фиксируем время до остановки.
        if acc.get("started_at"):
            accumulate_runtime(acc)

        # Отменяем keepalive.
        if cs_name:

            tasks = context.bot_data.get(
                "keepalive_tasks",
                {}
            )

            task = tasks.pop(
                cs_name,
                None
            )

            if task:
                task.cancel()

        # Останавливаем Codespace.
        if cs_name and token:

            await asyncio.to_thread(
                gh_codespace_stop,
                cs_name,
                token
            )

        acc["active"] = False

        save_accounts(accounts)

        # Если остановили текущий,
        # пытаемся запустить следующий.
        if idx == get_current_index():

            next_idx = find_next_available_account(
                accounts
            )

            if next_idx != idx:

                await switch_to_account(
                    accounts,
                    next_idx,
                    context
                )

        await query.message.edit_text(
            f"⏹ Аккаунт {idx + 1} остановлен."
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # MAKE CURRENT
    # --------------------------------------------------------

    if data.startswith(
        "cs_make_current_"
    ):

        try:
            idx = int(
                data.split("_")[3]
            )
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]

        token = get_account_token(
            acc
        )

        if not token:

            await query.message.edit_text(
                "❌ У аккаунта нет токена."
            )
            return

        status = get_account_status(
            acc,
            token
        )

        if status["status"] != "running":

            await query.message.edit_text(
                "⚠️ Этот аккаунт не запущен."
            )
            return

        if idx == get_current_index():

            await query.message.edit_text(
                "ℹ️ Этот аккаунт уже текущий."
            )

            return

        await query.message.edit_text(
            "⏳ Переключаю..."
        )

        success, msg = await switch_to_account(
            accounts,
            idx,
            context
        )

        await query.message.edit_text(
            msg,
            parse_mode=ParseMode.HTML
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------

    if data.startswith("cs_del_"):

        try:
            idx = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):
            return

        if idx < 0 or idx >= len(accounts):
            return

        acc = accounts[idx]

        cs_name = acc.get(
            "codespace_name"
        )

        token = get_account_token(
            acc
        )

        # Фиксируем время.
        if acc.get("started_at"):
            accumulate_runtime(acc)

        # Останавливаем keepalive.
        if cs_name:

            tasks = context.bot_data.get(
                "keepalive_tasks",
                {}
            )

            task = tasks.pop(
                cs_name,
                None
            )

            if task:
                task.cancel()

        # Удаляем Codespace.
        if cs_name and token:

            await asyncio.to_thread(
                gh_codespace_delete,
                cs_name,
                token
            )

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

        await query.message.edit_text(
            f"🗑 Аккаунт "
            f"{escape_html(removed.get('name', ''))} "
            f"удалён."
        )

        await show_server(
            query.message,
            context
        )

        return

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    if data == "cs_back":

        await show_server(
            query.message,
            context
        )

        return


# ============================================================
# ФОНОВЫЕ ЗАДАЧИ
# ============================================================

async def auto_rotate_task(
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Проверяет текущий аккаунт и при необходимости переключает."""

    accounts = load_accounts()

    if not accounts:
        return

    current_idx = get_current_index()

    if current_idx >= len(accounts):
        current_idx = 0
        set_current_index(0)

    acc = accounts[current_idx]

    token = get_account_token(
        acc
    )

    if not token:
        print(
            f"⚠️ У текущего аккаунта "
            f"{current_idx + 1} нет токена."
        )
        return

    status = get_account_status(
        acc,
        token
    )

    # Сохраняем состояние, если get_account_status
    # обнаружил изменения.
    save_accounts(accounts)

    if status["hours_left"] <= 1.0:

        print(
            f"⏰ У аккаунта "
            f"{current_idx + 1} осталось "
            f"{status['hours_left']:.1f} ч."
        )

        next_idx = find_next_available_account(
            accounts
        )

        if next_idx == current_idx:
            print(
                "⚠️ Другого доступного аккаунта нет."
            )
            return

        success, msg = await switch_to_account(
            accounts,
            next_idx,
            context
        )

        if success:
            print(
                f"✅ {msg}"
            )
        else:
            print(
                f"❌ {msg}"
            )


async def keepalive_task(
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Резервная проверка keepalive.

    Основной keepalive работает через asyncio task.
    """

    accounts = load_accounts()

    if not accounts:
        return

    current_idx = get_current_index()

    if current_idx >= len(accounts):
        return

    acc = accounts[current_idx]

    if not acc.get("active"):
        return

    cs_name = acc.get(
        "codespace_name"
    )

    token = get_account_token(
        acc
    )

    if not cs_name or not token:
        return

    tasks = context.bot_data.setdefault(
        "keepalive_tasks",
        {}
    )

    task = tasks.get(
        cs_name
    )

    # Если основная задача уже существует,
    # ничего дополнительно не делаем.
    if task and not task.done():
        return

    await start_keepalive_for_account(
        cs_name,
        token,
        context
    )


# ============================================================
# REGISTRATION
# ============================================================

def register_codespace_handlers(
    app
) -> None:
    """
    Регистрирует Telegram handlers и фоновые задачи.

    Для JobQueue требуется:
    pip install "python-telegram-bot[job-queue]"
    """

    app.add_handler(
        CommandHandler(
            "server",
            cmd_server
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cs_callback,
            pattern=r"^cs_"
        )
    )

    job_queue = app.job_queue

    if job_queue is None:

        print(
            "⚠️ JobQueue недоступен.\n"
            "Для фоновых задач установи:\n"
            'pip install "python-telegram-bot[job-queue]"'
        )

        return

    job_queue.run_repeating(
        keepalive_task,
        interval=KEEPALIVE_INTERVAL * 60,
        first=60,
        name="codespace_keepalive"
    )

    job_queue.run_repeating(
        auto_rotate_task,
        interval=CHECK_INTERVAL,
        first=30,
        name="codespace_auto_rotate"
    )

    print(
        "✅ Codespace Manager "
        "зарегистрирован"
    )


# ============================================================
# СОЗДАНИЕ JSON
# ============================================================

def init_codespace_file() -> None:
    """Создаёт пример JSON, если файла нет."""

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

        with open(
            TOKENS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                example,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"📄 Создан файл "
            f"{TOKENS_FILE}"
        )

    except OSError as e:

        print(
            f"❌ Не удалось создать "
            f"{TOKENS_FILE}: {e}"
        )


# ============================================================
# INIT
# =====
=======================================================

init_codespace_file()
