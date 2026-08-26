from pathlib import Path

p = Path("бот.py")
s = p.read_text(encoding="utf-8")

old = '    if text.startswith("очко ") or text.startswith("21 "):\n'
new = '''    if text == "очко" or text == "21":
        await update.message.reply_text(
            f"🥶 {user_link(uid, user['username'])}, ты ввел что-то неправильно!\\n"
            f"<code>·····················</code>\\n"
            f"<u>♠️ 21/очко <b>[ставка]</b></u>",
            parse_mode=ParseMode.HTML
        )
        return

    if text.startswith("очко ") or text.startswith("21 "):\n'''
if old not in s:
    raise SystemExit("Не найден обработчик очко/21")
s = s.replace(old, new, 1)

replacements = {
    '    if text.startswith("боулинг"):\n': '    if text == "боулинг" or text == "бо" or text.startswith("боулинг ") or text.startswith("бо "):\n',
    '    if text.startswith("баскетбол"):\n': '    if text == "баскетбол" or text == "бс" or text.startswith("баскетбол ") or text.startswith("бс "):\n',
    '    if text.startswith("дартс"):\n': '    if text == "дартс" or text == "дс" or text.startswith("дартс ") or text.startswith("дс "):\n',
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit(f"Не найдено: {old!r}")
    s = s.replace(old, new, 1)

old = '''    if text == "баскетбол" or text == "бс" or text.startswith("баскетбол ") or text.startswith("бс "):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(f"Пример: <code>Баскетбол [ставка]</code>", parse_mode=ParseMode.HTML)
            return
'''
new = '''    if text == "баскетбол" or text == "бс" or text.startswith("баскетбол ") or text.startswith("бс "):
        parts_g = raw.split()
        if len(parts_g) < 2:
            await update.message.reply_text(
                f"🥶 {user_link(uid, user['username'])}, ты ввел что-то неправильно!\\n"
                f"<code>·····················</code>\\n"
                f"<u>♠️ 21/очко <b>[ставка]</b></u>",
                parse_mode=ParseMode.HTML
            )
            return
'''
if old not in s:
    raise SystemExit("Не найден блок баскетбола")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("OK")