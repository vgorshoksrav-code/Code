import asyncio
import threading
from bot import dp, bot
from api import app
import uvicorn
from database import init_db

async def start_bot():
    # Удаляем webhook перед polling — решает TelegramConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook удалён, запускаем polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка бота: {e}")

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    init_db()
    print("БД инициализирована")
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    print("API запущен на порту 8000")
    print("Telegram бот запускается...")
    asyncio.run(start_bot())
