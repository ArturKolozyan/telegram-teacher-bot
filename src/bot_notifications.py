"""
Telegram бот только для уведомлений ученикам
Админ-функции убраны, управление через веб-интерфейс
"""
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

import database as db
import scheduler as sched

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

router = Router()

# FSM состояния
class StudentRegistration(StatesGroup):
    waiting_for_timezone = State()

class HomeworkReason(StatesGroup):
    waiting_for_reason = State()

# === Команда /start для учеников ===

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Постоянная клавиатура
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📅 Мои уроки")]],
        resize_keyboard=True
    )
    
    # Проверяем зарегистрирован ли ученик
    student = await db.get_student(user_id)
    
    if student:
        await message.answer("👋 Добро пожаловать!", reply_markup=reply_keyboard)
        await show_student_menu(message)
    else:
        # Регистрация
        await message.answer(
            "👋 Привет! Я бот-помощник для учеников.\n\n"
            "Для начала укажи свой часовой пояс:",
            reply_markup=reply_keyboard
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="UTC+1", callback_data="tz_1"),
                InlineKeyboardButton(text="UTC+2", callback_data="tz_2"),
                InlineKeyboardButton(text="UTC+3 МСК", callback_data="tz_3")
            ],
            [
                InlineKeyboardButton(text="UTC+4", callback_data="tz_4"),
                InlineKeyboardButton(text="UTC+5", callback_data="tz_5"),
                InlineKeyboardButton(text="UTC+6", callback_data="tz_6")
            ]
        ])
        
        await message.answer("Выбери свой часовой пояс:", reply_markup=keyboard)
        await state.set_state(StudentRegistration.waiting_for_timezone)

# === Регистрация ученика ===

@router.callback_query(F.data.startswith("tz_"), StudentRegistration.waiting_for_timezone)
async def process_timezone_selection(callback: CallbackQuery, state: FSMContext):
    timezone_offset = int(callback.data.split("_")[1])
    
    user_id = callback.from_user.id
    name = callback.from_user.full_name
    username = callback.from_user.username or ""
    
    await db.add_student(user_id, name, username, timezone_offset)
    
    await callback.message.edit_text(
        f"✅ Регистрация завершена!\n\n"
        f"Твой часовой пояс: UTC+{timezone_offset}\n\n"
        f"Теперь ты будешь получать напоминания об уроках."
    )
    
    await state.clear()
    await show_student_menu(callback.message)

# === Меню ученика ===

async def show_student_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Мои уроки", callback_data="student_schedule")]
    ])
    
    await message.answer("Выбери действие:", reply_markup=keyboard)

@router.message(F.text == "📅 Мои уроки")
async def show_schedule_button(message: Message):
    await show_student_schedule_message(message)

@router.callback_query(F.data == "student_schedule")
async def show_student_schedule(callback: CallbackQuery):
    await show_student_schedule_message(callback.message)
    await callback.answer()

async def show_student_schedule_message(message: Message):
    user_id = message.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        await message.answer("Ошибка: ты не зарегистрирован")
        return
    
    schedule = await db.get_student_schedule(user_id)
    
    if not schedule:
        await message.answer("📅 У тебя пока нет уроков в расписании.")
        return
    
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    user_tz_offset = student['timezone_offset']
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    # Группируем по дням
    schedule_by_day = {}
    for lesson in schedule:
        day = lesson['day']
        if day not in schedule_by_day:
            schedule_by_day[day] = []
        schedule_by_day[day].append(lesson['time'])
    
    message_text = "📅 Твои уроки на неделю:\n\n"
    
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    for day in days_order:
        if day in schedule_by_day:
            message_text += f"📌 {day_names_ru[day]}\n"
            for time in sorted(schedule_by_day[day]):
                # Конвертируем время
                hour, minute = map(int, time.split(':'))
                time_diff = user_tz_offset - admin_tz_offset
                user_hour = (hour + time_diff) % 24
                user_time = f"{user_hour:02d}:{minute:02d}"
                
                message_text += f"   ⏰ {user_time}\n"
            message_text += "\n"
    
    await message.answer(message_text)

# === Обработка ответов по ДЗ ===

@router.callback_query(F.data.startswith("hw_done_"))
async def process_homework_done(callback: CallbackQuery):
    parts = callback.data.split("_")
    date = parts[2]
    time = parts[3]
    user_id = callback.from_user.id
    
    await db.save_homework_response(date, time, user_id, "done")
    
    await callback.message.edit_text("✅ Отлично! Домашнее задание выполнено.")
    await callback.answer()

@router.callback_query(F.data.startswith("hw_not_done_"))
async def process_homework_not_done(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    date = parts[3]
    time = parts[4]
    
    await state.update_data(lesson_date=date, lesson_time=time)
    await state.set_state(HomeworkReason.waiting_for_reason)
    
    await callback.message.edit_text("Напиши причину, почему домашнее задание не выполнено:")
    await callback.answer()

@router.message(HomeworkReason.waiting_for_reason)
async def process_homework_reason(message: Message, state: FSMContext):
    reason = message.text
    data = await state.get_data()
    date = data['lesson_date']
    time = data['lesson_time']
    user_id = message.from_user.id
    
    await db.save_homework_response(date, time, user_id, "not_done", reason)
    
    await message.answer("✅ Спасибо, информация сохранена.")
    await state.clear()

async def main():
    # Создаем папку data если её нет
    db.ensure_data_dir()
    
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(router)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    
    # Получаем ADMIN_ID из .env для отправки отчетов
    admin_id = int(os.getenv('ADMIN_ID', 0))
    
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
        args=[bot, admin_id]
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
        args=[bot, admin_id]
    )
    
    scheduler.start()
    logger.info("Планировщик запущен")
    
    # Запуск бота
    logger.info("Бот запущен (только уведомления)")
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
