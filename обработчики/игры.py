"""Общая логика игр: очко и крестики-нолики.

Telegram-обработчики будут подключены после переноса маршрутизации из монолита.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CARD_DECK = [(value, suit) for suit in ("♠️", "♥️", "♦️", "♣️")
             for value in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")]


def card_value(card: tuple[str, str]) -> int:
    return 10 if card[0] in ("J", "Q", "K") else 11 if card[0] == "A" else int(card[0])


def hand_value(hand: list[tuple[str, str]]) -> int:
    total = sum(card_value(card) for card in hand)
    aces = sum(card[0] == "A" for card in hand)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def hand_str(hand: list[tuple[str, str]]) -> str:
    return " • ".join(f"{value}{suit}" for value, suit in hand)


def ho_board_text(board: list[str], bet: int, p1_name: str, p2_name: str) -> str:
    cells = [cell or "▫️" for cell in board]
    return (
        f"❌⭕ Крестики-нолики • ставка {bet}\n"
        f"{p1_name} — ❌ | {p2_name} — ⭕\n\n"
        f"{cells[0]} {cells[1]} {cells[2]}\n"
        f"{cells[3]} {cells[4]} {cells[5]}\n"
        f"{cells[6]} {cells[7]} {cells[8]}"
    )


def ho_check_winner(board: list[str]) -> str | None:
    lines = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
    for a, b, c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return "draw" if all(board) else None


def ho_keyboard(game_id: str, board: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for row in range(3):
        buttons.append([
            InlineKeyboardButton(board[row * 3 + col] or "▫️", callback_data=f"ho_{game_id}_{row * 3 + col}")
            for col in range(3)
        ])
    return InlineKeyboardMarkup(buttons)
