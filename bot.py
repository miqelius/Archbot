import os
import importlib
import pkgutil
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from google import genai
from core.core_config import settings
import routers

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

# Gemini კლიენტის ინიციალიზაცია გარემოს ცვლადიდან
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer("გამარჯობა! ბოტი წარმატებით მუშაობს Render-ზე და მზადაა თარგმნისთვის! 🚀")

@dp.message(F.text & ~F.text.startswith("/"))
async def translation_handler(message: Message) -> None:
    user_text = message.text
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"თარგმნე და დაამუშავე პროფესიონალურად: {user_text}",
        )
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"შეცდომა თარგმნისას: {e}")

# დინამიური როუტერების ჩატვირთვა
try:
    for _, module_name, _ in pkgutil.iter_modules(routers.__path__):
        module = importlib.import_module(f"routers.{module_name}")
        if hasattr(module, "router"):
            dp.include_router(module.router)
except Exception:
    pass
