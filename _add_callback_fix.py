from pathlib import Path
p = Path('бот.py')
s = p.read_text(encoding='utf-8')
marker = '    if data == "create_bunker":\n'
block = '''    if data.startswith("admin_promo_type_"):
        if uid not in ADMIN_IDS:
            await query.answer("Нет доступа.", show_alert=True)
            return
        reward_t = data[len("admin_promo_type_"):].lower()
        if reward_t not in {"coins", "bottles", "rating", "bbcoins", "exp"}:
            await query.answer("Неизвестный тип награды.", show_alert=True)
            return
        context.user_data["admin_promo_reward_type"] = reward_t
        await query.answer()
        labels = {"coins": "💰 крышки", "bottles": "🍾 бутылки", "exp": "⭐️ опыт", "rating": "🏆 рейтинг", "bbcoins": "🪙 BB-coins"}
        await query.message.reply_text(
            f"Выбрано: {labels[reward_t]}.\\n"
            "Теперь отправьте: <code>код сумма [использований]</code>\\n"
            "Если количество использований не указать, будет 1. Один пользователь сможет использовать промокод только один раз.",
            parse_mode=ParseMode.HTML
        )
        return

    if data == "create_bunker":
'''
if marker not in s:
    raise SystemExit('callback insertion marker not found')
s = s.replace(marker, block, 1)
p.write_text(s, encoding='utf-8')
