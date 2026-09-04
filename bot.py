from aiogram import Bot, Dispatcher
from core.core_config import settings

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()
