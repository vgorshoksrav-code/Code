import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, SUPER_ADMINS
from database import create_or_update_user
from admin_utils import is_admin, add_admin, remove_admin, get_all_skins, give_skin_to_user, add_stars_to_user, get_webapp_url, set_webapp_url

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Клавиатура с кнопками Mini App
async def main_keyboard():
    webapp_url = get_webapp_url()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Сразиться", web_app=WebAppInfo(url=f"{webapp_url}?startapp=duel"))],
        [InlineKeyboardButton(text="📊 Лидеры", web_app=WebAppInfo(url=f"{webapp_url}?startapp=leaderboard"))],
        [InlineKeyboardButton(text="👤 Мой герой", web_app=WebAppInfo(url=f"{webapp_url}?startapp=hero"))],
        [InlineKeyboardButton(text="✨ Лавка", web_app=WebAppInfo(url=f"{webapp_url}?startapp=shop"))]
    ])
    return keyboard

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].split("_")[1])
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    create_or_update_user(user_id, username)
    if referrer_id and referrer_id != user_id:
        from database import get_db_connection
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id, reward_claimed) VALUES (?, ?, 0)", (referrer_id, user_id))
        conn.commit()
        conn.close()
    await message.answer(
        "🔮 *Эхарис: Дуэль душ*\\!\n\nПриветствую, избранник\\! Твоя душа вплетена в эхо вечности\\.\n\n"
        "Сражайся с другими, собирай скины, улучшай навыки и стань легендой\\!\n\n"
        "Используй кнопки ниже, чтобы открыть игру\\.",
        reply_markup=await main_keyboard(),
        parse_mode="MarkdownV2"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🌀 *Правила игры*:\\n\\n"
        "• Ты участвуешь в PvP\\-дуэлях с другими игроками или AI\\.\\n"
        "• У тебя есть энергия, которая восстанавливается со временем\\.\\n"
        "• Используй скилы, чтобы наносить урон или лечиться\\.\\n"
        "• Победа приносит осколки и повышает рейтинг\\.\\n"
        "• Приглашай друзей и получай ценные награды \\(цепные бонусы\\)\\.\\n"
        "• Покупай скины за Telegram Stars и становись VIP\\.\\n\\n"
        "Удачи на арене\\!"
    )
    await message.answer(help_text, parse_mode="MarkdownV2")

# Команда для суперадмина: установить URL веб-приложения
@dp.message(Command("setwebapp"))
async def cmd_setwebapp(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS:
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /setwebapp <https://новый-url.amvera.io>")
        return
    new_url = args[1]
    if not new_url.startswith("http"):
        await message.answer("URL должен начинаться с http:// или https://")
        return
    set_webapp_url(new_url)
    await message.answer(f"✅ URL веб-приложения обновлён на:\n{new_url}\n\nТеперь все кнопки будут вести на новый адрес.")

# Админ-команды
@dp.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS:
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /addadmin <user_id>")
        return
    try:
        new_admin_id = int(args[1])
        add_admin(new_admin_id, message.from_user.id)
        await message.answer(f"✅ Пользователь {new_admin_id} теперь администратор.")
    except:
        await message.answer("Ошибка: неверный ID.")

@dp.message(Command("removeadmin"))
async def cmd_removeadmin(message: types.Message):
    if message.from_user.id not in SUPER_ADMINS:
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /removeadmin <user_id>")
        return
    try:
        admin_id = int(args[1])
        remove_admin(admin_id)
        await message.answer(f"✅ Администратор {admin_id} удалён.")
    except:
        await message.answer("Ошибка.")

@dp.message(Command("skins"))
async def cmd_skins(message: types.Message):
    if not (message.from_user.id in SUPER_ADMINS or is_admin(message.from_user.id)):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    skins = get_all_skins()
    text = "📦 *Список скинов:*\n\n"
    for s in skins:
        bonus = s['stat_bonus'] if s['stat_bonus'] else "{}"
        text += f"ID: {s['id']} | {s['name']} | {s['rarity']} | {s['price_stars']} ⭐️ | бонус: {bonus}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("giveskin"))
async def cmd_giveskin(message: types.Message):
    if not (message.from_user.id in SUPER_ADMINS or is_admin(message.from_user.id)):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /giveskin <user_id> <skin_id>")
        return
    try:
        user_id = int(args[1])
        skin_id = int(args[2])
        give_skin_to_user(user_id, skin_id)
        await message.answer(f"✅ Скин ID {skin_id} выдан пользователю {user_id}.")
    except:
        await message.answer("Ошибка.")

@dp.message(Command("addstars"))
async def cmd_addstars(message: types.Message):
    if not (message.from_user.id in SUPER_ADMINS or is_admin(message.from_user.id)):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /addstars <user_id> <amount>")
        return
    try:
        user_id = int(args[1])
        amount = int(args[2])
        add_stars_to_user(user_id, amount)
        await message.answer(f"✅ Добавлено {amount} звёзд пользователю {user_id}.")
    except:
        await message.answer("Ошибка.")
