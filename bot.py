from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from core.core_config import settings
import importlib
import pkgutil
import routers

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

# გარანტირებული ტესტური ჰენდლერები (რომ დარწმუნდეთ მუშაობაში)
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"გამარჯობა! ბოტი წარმატებით მუშაობს Render-ზე! 🚀")

@dp.message(F.text)
async def echo_handler(message: Message) -> None:
    await message.answer(f"მოგიწოდებთ: {message.text}")

# დინამიური როუტერების ჩატვირთვა (თუ სხვებიც გაქვთ)
try:
    for _, module_name, _ in pkgutil.iter_modules(routers.__path__):
        module = importlib.import_module(f"routers.{module_name}")
        if hasattr(module, "router"):
            dp.include_router(module.router)
except Exception:
    pass
