import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from .config import config
from .middlewares import DbSessionMiddleware, AuthMiddleware
from .handlers import router

async def main():
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    storage = RedisStorage.from_url(config.redis_url)
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware
    dp.message.middleware(AuthMiddleware())
    dp.message.middleware(DbSessionMiddleware())
    
    # Регистрация роутеров
    dp.include_router(router)
    
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
