from pathlib import Path
import re

p = Path('бот.py')
s = p.read_text(encoding='utf-8')

# Fix bare 21/очко: show the requested error instead of silently returning.
old = '''    if text == "очко" or text == "21" or text.startswith("очко ") or text.startswith("21 "):
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
'''
new = '''    if text == "очко" or text == "21" or text.startswith("очко ") or text.startswith("21 "):
        parts_o = raw.split()
        if len(parts_o) >= 2:
            bet = parse_bet(parts_o[1], user["balance"])
            if bet > 0:
                await handle_ochko_start(update, user, bet)
            else:
                await update.message.reply_text(
                    f"🥶 {user_link(uid, user['username'])}, ты ввел что-то неправильно!\\n"
                    f"<code>·····················</code>\\n"
                    f"<u>♠️ 21/очко <b>[ставка]</b></u>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                f"🥶 {user_link(uid, user['username'])}, ты ввел что-то неправильно!\\n"
                f"<code>·····················</code>\\n"
                f"<u>♠️ 21/очко <b>[ставка]</b></u>",
                parse_mode=ParseMode.HTML
            )
        return
'''
if old not in s:
    raise SystemExit('21 block not found')
s = s.replace(old, new, 1)

# The game cooldown is already exactly 3 seconds in check_cooldown(); keep it unchanged.

# Short result messages for Telegram dice games.
patterns = [
    (
        re.compile(r'''        await update\.message\.reply_text\(\n            f"🎳 \{user_link\(uid, user\['username'\]\)\}, \{desc\}\\n"\n            f"· · · · · · · · · · · · · · ·\\n"\n            f"💸 Ставка: \{fmt_smart\(bet\)\} кр\.\\n"\n            \+ \(f"🎉 Выигрыш: \{fmt_smart\(win\)\} кр\." if change > 0 else f"📊 Итог: \{sign\}\{fmt_smart\(change\)\} кр\."\),\n            parse_mode=ParseMode\.HTML\n        \)'''),
        '''        result_text = f"✅ Твой выигрыш составил <b>{fmt_smart(change)}</b> кр.!" if change > 0 else "🛑 Ты проиграл(-а)! Попытай удачу в следующий раз 😣"
        await update.message.reply_text(
            f"{user_link(uid, user['username'])}\\n🎳 Выпало - {pins}\\n{result_text}",
            parse_mode=ParseMode.HTML
        )''',
        'bowling',
    ),
    (
        re.compile(r'''        await update\.message\.reply_text\(\n            f"🏀 \{user_link\(uid, user\['username'\]\}, \{desc\}\\n"\n            f"· · · · · · · · · · · · · · ·\\n"\n            f"💸 Ставка: \{fmt_smart\(bet\)\} кр\.\\n"\n            \+ \(f"🎉 Выигрыш: \{fmt_smart\(win\)\} кр\." if change > 0 else f"📊 Итог: \{sign\}\{fmt_smart\(change\)\} кр\."\),\n            parse_mode=ParseMode\.HTML\n        \)'''),
        '''        result_text = f"✅ Твой выигрыш составил <b>{fmt_smart(change)}</b> кр.!" if change > 0 else "🛑 Ты проиграл(-а)! Попытай удачу в следующий раз 😣"
        await update.message.reply_text(
            f"{user_link(uid, user['username'])}\\n🏀 Выпало - {roll}\\n{result_text}",
            parse_mode=ParseMode.HTML
        )''',
        'basketball',
    ),
    (
        re.compile(r'''        await update\.message\.reply_text\(\n            f"🎯 \{user_link\(uid, user\['username'\]\)\}, \{desc\}\\n"\n            f"· · · · · · · · · · · · · · ·\\n"\n            f"💸 Ставка: \{fmt_smart\(bet\)\} кр\.\\n"\n            f"\{result_line\}",\n            parse_mode=ParseMode\.HTML\n        \)'''),
        '''        result_text = f"✅ Твой выигрыш составил <b>{fmt_smart(change)}</b> кр.!" if change > 0 else "🛑 Ты проиграл(-а)! Попытай удачу в следующий раз 😣"
        await update.message.reply_text(
            f"{user_link(uid, user['username'])}\\n🎯 Выпало - {roll}\\n{result_text}",
            parse_mode=ParseMode.HTML
        )''',
        'darts',
    ),
]
for pattern, replacement, name in patterns:
    s, count = pattern.subn(replacement, s, count=1)
    if count != 1:
        raise SystemExit(f'{name} output block not found')

p.write_text(s, encoding='utf-8')
