import asyncio
import threading
from bot import dp, bot
from api import app
import uvicorn
from database import init_db

async def start_bot():
    await dp.start_polling(bot)

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=start_api, daemon=True).start()
    asyncio.run(start_bot())
