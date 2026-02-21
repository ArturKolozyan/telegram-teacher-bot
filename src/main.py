import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

import database as db
import handlers
import scheduler as sched

# Загружаем переменные окружения
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    # Создаем папку data если её нет
    db.ensure_data_dir()
    
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Передаем admin_id в роутер
    dp['admin_id'] = ADMIN_ID
    
    dp.include_router(handlers.router)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    
    # Проверка напоминаний каждую минуту
    scheduler.add_job(
        sched.check_and_send_reminders,
        'cron',
        minute='*',
        args=[bot]
    )
    
    # Проверка отчетов по ДЗ каждую минуту
    scheduler.add_job(
        sched.check_and_send_homework_reports,
        'cron',
        minute='*',
        args=[bot, ADMIN_ID]
    )
    
    # Ежедневное напоминание админу
    settings = await db.get_settings()
    reminder_time = settings['admin_daily_reminder_time']
    hour, minute = map(int, reminder_time.split(':'))
    
    scheduler.add_job(
        sched.send_admin_daily_reminder,
        'cron',
        hour=hour,
        minute=minute,
        args=[bot, ADMIN_ID]
    )
    
    scheduler.start()
    logger.info("Планировщик запущен")
    
    # Запуск бота
    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
