import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from .config import config
from .database import engine
from .models import Base
from .middlewares import DbSessionMiddleware, AuthMiddleware
from .handlers import router

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="projects", description="📂 Мои проекты"),
        BotCommand(command="stats", description="📊 Финансы и статистика"),
        BotCommand(command="help", description="ℹ️ Справка и быстрые команды"),
        BotCommand(command="cancel", description="❌ Отменить текущее действие"),
    ]
    await bot.set_my_commands(commands)

async def init_database():
    logging.info("Ensuring database tables exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    storage = RedisStorage.from_url(config.redis_url)
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware для сообщений и callback-кнопок
    dp.message.middleware(AuthMiddleware())
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    
    # Регистрация роутеров
    dp.include_router(router)
    
    # Инициализация базы данных и команд меню
    try:
        await init_database()
    except Exception as e:
        logging.warning(f"Could not auto-create tables: {e}")
        
    await setup_bot_commands(bot)
    
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
