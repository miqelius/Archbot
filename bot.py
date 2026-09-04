from aiogram import Bot, Dispatcher, Router
from core.core_config import settings
import importlib
import pkgutil
import routers

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

for _, module_name, _ in pkgutil.iter_modules(routers.__path__):
    module = importlib.import_module(f"routers.{module_name}")
    if hasattr(module, "router") and isinstance(module.router, Router):
        dp.include_router(module.router)
