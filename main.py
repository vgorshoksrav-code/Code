import asyncio
import threading
from bot import dp, bot
from api import app
import uvicorn
from database import init_db

async def start_bot():
    """Запускает Telegram бота в режиме polling"""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка в боте: {e}")

def start_api():
    """Запускает FastAPI сервер на всех интерфейсах"""
    # ВАЖНО: host="0.0.0.0" - обязательно для Amvera
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    # Инициализация базы данных
    init_db()
    print("База данных инициализирована")

    # Запуск API в отдельном потоке
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    print("API сервер запущен на порту 8000")

    # Запуск бота (основной поток)
    print("Telegram бот запущен")
    asyncio.run(start_bot())
