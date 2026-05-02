import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from config import BOT_TOKEN, SUPER_ADMINS
from database import create_or_update_user, get_user, update_user_field, add_skin_to_user, get_db_connection
from admin_utils import is_admin, add_admin, remove_admin, get_all_skins, give_skin_to_user, add_stars_to_user, get_webapp_url, set_webapp_url

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# ── Keyboards ────────────────────────────────────────────────────────────

async def main_keyboard():
    url = get_webapp_url()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Сразиться",  web_app=WebAppInfo(url=f"{url}?startapp=duel"))],
        [InlineKeyboardButton(text="🏰 Кампания",   web_app=WebAppInfo(url=f"{url}?startapp=campaign")),
         InlineKeyboardButton(text="🏛️ Гильдия",   web_app=WebAppInfo(url=f"{url}?startapp=guild"))],
        [InlineKeyboardButton(text="👤 Мой герой",  web_app=WebAppInfo(url=f"{url}?startapp=hero")),
         InlineKeyboardButton(text="📊 Лидеры",     web_app=WebAppInfo(url=f"{url}?startapp=leaderboard"))],
        [InlineKeyboardButton(text="✨ Лавка",      web_app=WebAppInfo(url=f"{url}?startapp=shop"))],
    ])

# ── /start ────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try: referrer_id = int(args[1].split("_")[1])
        except: pass

    user_id  = message.from_user.id
    uname    = message.from_user.username or f"user_{user_id}"
    is_new   = create_or_update_user(user_id, uname)

    if referrer_id and referrer_id != user_id:
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO referrals (referrer_id,referred_id,reward_claimed) VALUES (?,?,0)",
                     (referrer_id, user_id))
        conn.commit(); conn.close()

    await message.answer(
        "🔮 *Эхарис: Дуэль душ*\\!\n\n"
        "Приветствую, избранник\\! Твоя душа вплетена в эхо вечности\\.\n\n"
        "Сражайся с другими, собирай скины, улучшай навыки и стань легендой\\!\n\n"
        "Используй кнопки ниже, чтобы открыть игру\\.",
        reply_markup=await main_keyboard(),
        parse_mode="MarkdownV2"
    )

# ── /help ──────────────────────────────────────────────────────────────────

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🌀 *Правила игры:*\n\n"
        "• PvP-дуэли с игроками или AI\n"
        "• Энергия восстанавливается автоматически\n"
        "• Победа → осколки 💎 и рейтинг\n"
        "• PvE-кампания: 10 глав, 30 боссов\n"
        "• Гильдии: рейды, квесты, чат\n"
        "• Скины за Telegram Stars ⭐\n"
        "• Промокоды от администраторов\n"
        "• Ежедневный подарок каждые 24ч\n\n"
        "Реферальная ссылка: /ref",
        parse_mode="Markdown"
    )

# ── /ref ──────────────────────────────────────────────────────────────────

@dp.message(Command("ref"))
async def cmd_ref(message: types.Message):
    uid  = message.from_user.id
    url  = get_webapp_url()
    link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{uid}"
    await message.answer(
        f"🔗 *Ваша реферальная ссылка:*\n{link}\n\n"
        "За каждого приглашённого друга вы получите:\n"
        "1-й друг: +50 💎 осколков\n"
        "2-й друг: +100 💎 + скин\n"
        "3-й друг: +200 💎 + прокачка скилла\n"
        "4+ друзей: +20 💎 + 1 🎟️ билет",
        parse_mode="Markdown"
    )

# ── /admin — показывает команды если пользователь администратор ────────────

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    uid = message.from_user.id
    if uid not in SUPER_ADMINS and not is_admin(uid):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    is_super = uid in SUPER_ADMINS
    text = "🛡️ *Панель администратора*\n\n"
    text += "*Управление пользователями:*\n"
    text += "`/giveskin <user_id> <skin_id>` — выдать скин\n"
    text += "`/addstars <user_id> <amount>` — добавить Stars (stars_spent)\n"
    text += "`/addshards <user_id> <amount>` — добавить осколки\n"
    text += "`/skins` — список всех скинов\n\n"
    text += "*Промокоды:*\n"
    text += "`/newpromo <code> <type> <value> [max_uses] [days]`\n"
    text += "  Типы: `shards`, `tickets`, `skin`, `temp_skin`, `stars_spent`\n"
    text += "  Примеры:\n"
    text += "  `/newpromo WELCOME shards 500 100 30`\n"
    text += "  `/newpromo VIP2024 skin 7 10 7`\n"
    text += "  `/newpromo TRIAL temp_skin 13,72 50 3` (скин 13 на 72 часа)\n\n"
    text += "`/listpromos` — список активных промокодов\n"
    text += "`/delpromo <code>` — деактивировать промокод\n\n"
    text += "*Временные события:*\n"
    text += "`/newevent <name> <type> <multiplier> <hours>`\n"
    text += "  Типы: `double_shards`, `bonus_skin`, `extra_tickets`\n"
    text += "  Пример: `/newevent \"Двойные осколки\" double_shards 2.0 48`\n"
    text += "`/listevents` — список событий\n\n"
    if is_super:
        text += "*Только суперадмин:*\n"
        text += "`/addadmin <user_id>` — добавить администратора\n"
        text += "`/removeadmin <user_id>` — удалить администратора\n"
        text += "`/setwebapp <url>` — изменить URL мини-аппа\n"
    await message.answer(text, parse_mode="Markdown")

# ── /skins ─────────────────────────────────────────────────────────────────

@dp.message(Command("skins"))
async def cmd_skins(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    skins = get_all_skins()
    text  = "📦 *Скины:*\n\n"
    for s in skins:
        text += f"ID:{s['id']} | {s['name']} | {s['rarity']} | {s['price_stars']}⭐\n"
    await message.answer(text, parse_mode="Markdown")

# ── /giveskin ──────────────────────────────────────────────────────────────

@dp.message(Command("giveskin"))
async def cmd_giveskin(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /giveskin <user_id> <skin_id>"); return
    try:
        give_skin_to_user(int(args[1]), int(args[2]))
        await message.answer(f"✅ Скин {args[2]} → пользователю {args[1]}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# ── /addstars ──────────────────────────────────────────────────────────────

@dp.message(Command("addstars"))
async def cmd_addstars(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /addstars <user_id> <amount>"); return
    try:
        add_stars_to_user(int(args[1]), int(args[2]))
        await message.answer(f"✅ +{args[2]} Stars → {args[1]}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# ── /addshards ─────────────────────────────────────────────────────────────

@dp.message(Command("addshards"))
async def cmd_addshards(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /addshards <user_id> <amount>"); return
    try:
        uid, amt = int(args[1]), int(args[2])
        u = get_user(uid)
        if u:
            update_user_field(uid, 'shards', u['shards'] + amt)
            await message.answer(f"✅ +{amt} 💎 → {uid}")
        else:
            await message.answer("Пользователь не найден")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# ── /newpromo ──────────────────────────────────────────────────────────────

@dp.message(Command("newpromo"))
async def cmd_newpromo(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer(
            "Использование:\n"
            "/newpromo <CODE> <type> <value> [max_uses=1] [days=30]\n\n"
            "Типы и значения:\n"
            "• shards 500\n"
            "• tickets 3\n"
            "• skin 7\n"
            "• temp_skin 7,72 (скин_id,часов)\n"
            "• stars_spent 200"
        ); return
    code   = parts[1]
    rtype  = parts[2]
    rval   = parts[3]
    max_u  = int(parts[4]) if len(parts) > 4 else 1
    days   = int(parts[5]) if len(parts) > 5 else 30

    if rtype in ('shards','tickets','stars_spent'):
        reward_value = {"amount": int(rval)}
    elif rtype == 'skin':
        reward_value = {"skin_id": int(rval)}
    elif rtype == 'temp_skin':
        sid, hrs = rval.split(',')
        reward_value = {"skin_id": int(sid), "hours": int(hrs)}
    else:
        await message.answer("Неверный тип награды"); return

    from promos import create_promo
    res = create_promo(code, rtype, reward_value, max_u, days, message.from_user.id)
    if res['success']:
        await message.answer(f"✅ Промокод `{code.upper()}` создан!\nТип: {rtype} | Награда: {reward_value} | Использований: {max_u} | Дней: {days}", parse_mode="Markdown")
    else:
        await message.answer(f"Ошибка: {res.get('error')}")

# ── /listpromos ────────────────────────────────────────────────────────────

@dp.message(Command("listpromos"))
async def cmd_listpromos(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    from promos import list_promos
    promos = list_promos()
    if not promos:
        await message.answer("Нет активных промокодов"); return
    text = "🎟️ *Активные промокоды:*\n\n"
    for p in promos:
        text += f"`{p['code']}` — {p['reward_type']} | {p['used_count']}/{p['max_uses']} | истекает: {p['expires_at'] or '∞'}\n"
    await message.answer(text, parse_mode="Markdown")

# ── /delpromo ──────────────────────────────────────────────────────────────

@dp.message(Command("delpromo"))
async def cmd_delpromo(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /delpromo <CODE>"); return
    from promos import deactivate_promo
    deactivate_promo(parts[1])
    await message.answer(f"✅ Промокод `{parts[1].upper()}` деактивирован", parse_mode="Markdown")

# ── /newevent ──────────────────────────────────────────────────────────────

@dp.message(Command("newevent"))
async def cmd_newevent(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    import shlex
    try:
        parts = shlex.split(message.text)[1:]
        if len(parts) < 4:
            raise ValueError
        name, etype, mult, hrs = parts[0], parts[1], float(parts[2]), int(parts[3])
    except:
        await message.answer(
            'Использование:\n/newevent "Название" <type> <multiplier> <hours>\n\n'
            'Типы: double_shards | bonus_skin | extra_tickets'
        ); return
    icons = {'double_shards':'💰','bonus_skin':'🎁','extra_tickets':'🎟️'}
    from promos import create_event
    create_event(name, f"Событие активно {hrs} часов", etype, mult, hrs,
                 icons.get(etype,'🎉'), message.from_user.id)
    await message.answer(f"✅ Событие «{name}» запущено на {hrs} часов!")

# ── /listevents ────────────────────────────────────────────────────────────

@dp.message(Command("listevents"))
async def cmd_listevents(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS and not is_admin(message.from_user.id):
        return
    from promos import list_events
    events = list_events()
    if not events:
        await message.answer("Нет событий"); return
    text = "🎉 *События:*\n\n"
    for e in events:
        status = "✅ Активно" if e['active'] else "❌"
        text += f"{e['icon']} {e['name']} | {e['event_type']} x{e['multiplier']} | {status}\n до {e['ends_at']}\n\n"
    await message.answer(text, parse_mode="Markdown")

# ── Superadmin only ────────────────────────────────────────────────────────

@dp.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS: return
    parts = message.text.split()
    if len(parts) != 2: await message.answer("Использование: /addadmin <user_id>"); return
    try:
        add_admin(int(parts[1]), message.from_user.id)
        await message.answer(f"✅ Пользователь {parts[1]} — администратор")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("removeadmin"))
async def cmd_removeadmin(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS: return
    parts = message.text.split()
    if len(parts) != 2: await message.answer("Использование: /removeadmin <user_id>"); return
    try:
        remove_admin(int(parts[1]))
        await message.answer(f"✅ Администратор {parts[1]} удалён")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("setwebapp"))
async def cmd_setwebapp(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS: return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("http"):
        await message.answer("Использование: /setwebapp <https://url>"); return
    set_webapp_url(parts[1])
    await message.answer(f"✅ URL обновлён: {parts[1]}")

# ── Telegram Stars payment ─────────────────────────────────────────────────

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message):
    """Quick purchase via Stars from bot chat."""
    await message.answer(
        "⭐ Покупка скинов через Telegram Stars\n\n"
        "Откройте Лавку в игре для покупки скинов!",
        reply_markup=await main_keyboard()
    )

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    """Handle successful Telegram Stars payment."""
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload  # "skin_7"
    stars   = message.successful_payment.total_amount

    user = get_user(uid)
    if not user: return

    new_stars = user['stars_spent'] + stars
    update_user_field(uid, 'stars_spent', new_stars)

    if payload.startswith("skin_"):
        skin_id = int(payload.split("_")[1])
        add_skin_to_user(uid, skin_id)
        conn = get_db_connection()
        skin = conn.execute("SELECT name FROM skins WHERE id=?", (skin_id,)).fetchone()
        conn.close()
        name = skin['name'] if skin else str(skin_id)
        if new_stars >= 5000 and not user['is_vip']:
            update_user_field(uid, 'is_vip', 1)
            add_skin_to_user(uid, 3)
            await message.answer(f"🎉 Скин «{name}» получен!\n👑 Вы стали VIP!")
        else:
            await message.answer(f"✅ Скин «{name}» добавлен в коллекцию!")
