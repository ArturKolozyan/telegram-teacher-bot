"""
Telegram бот для учеников и админа
"""
import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import pytz

import database as db
import scheduler as sched

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

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

# === КОМАНДА /start ===

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем - админ или ученик
    if user_id == ADMIN_ID:
        await show_admin_menu(message)
    else:
        # Проверяем зарегистрирован ли ученик
        student = await db.get_student(user_id)
        
        if student:
            await show_student_menu(message)
        else:
            await start_registration(message, state)

# === РЕГИСТРАЦИЯ УЧЕНИКА ===

async def start_registration(message: Message, state: FSMContext):
    """Начать регистрацию ученика"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="UTC -12, Веллингтон", callback_data="tz_-12"),
        ],
        [
            InlineKeyboardButton(text="UTC -11, Острова Мидуэй", callback_data="tz_-11"),
        ],
        [
            InlineKeyboardButton(text="UTC -10, Гонолулу", callback_data="tz_-10"),
        ],
        [
            InlineKeyboardButton(text="UTC -9, Анкоридж", callback_data="tz_-9"),
        ],
        [
            InlineKeyboardButton(text="UTC -8, Лос Анджелес", callback_data="tz_-8"),
        ],
        [
            InlineKeyboardButton(text="UTC -7, Денвер", callback_data="tz_-7"),
        ],
        [
            InlineKeyboardButton(text="UTC -6, Чикаго", callback_data="tz_-6"),
        ],
        [
            InlineKeyboardButton(text="UTC -5, Нью-Йорк", callback_data="tz_-5"),
        ],
        [
            InlineKeyboardButton(text="UTC -4, Санто-Доминго", callback_data="tz_-4"),
        ],
        [
            InlineKeyboardButton(text="UTC -3, Рио-Де-Жанейро", callback_data="tz_-3"),
        ],
        [
            InlineKeyboardButton(text="UTC -2, Гренландия", callback_data="tz_-2"),
        ],
        [
            InlineKeyboardButton(text="UTC -1, Азорские Острова", callback_data="tz_-1"),
        ],
        [
            InlineKeyboardButton(text="UTC +0, Лондон", callback_data="tz_0"),
        ],
        [
            InlineKeyboardButton(text="UTC +1, Кишинев, Париж", callback_data="tz_1"),
        ],
        [
            InlineKeyboardButton(text="UTC +2, Калининград, Киев", callback_data="tz_2"),
        ],
        [
            InlineKeyboardButton(text="UTC +3, Москва, Минск", callback_data="tz_3"),
        ],
        [
            InlineKeyboardButton(text="UTC +4, Самара, Баку", callback_data="tz_4"),
        ],
        [
            InlineKeyboardButton(text="UTC +5, Душанбе, Екатеринбург", callback_data="tz_5"),
        ],
        [
            InlineKeyboardButton(text="UTC +6, Бишкек, Астана", callback_data="tz_6"),
        ],
        [
            InlineKeyboardButton(text="UTC +7, Красноярск", callback_data="tz_7"),
        ],
        [
            InlineKeyboardButton(text="UTC +8, Иркутск, Пекин", callback_data="tz_8"),
        ],
        [
            InlineKeyboardButton(text="UTC +9, Якутск, Токио", callback_data="tz_9"),
        ],
        [
            InlineKeyboardButton(text="UTC +10, Владивосток", callback_data="tz_10"),
        ],
        [
            InlineKeyboardButton(text="UTC +11, Среднеколымск", callback_data="tz_11"),
        ],
        [
            InlineKeyboardButton(text="UTC +12, Камчатка", callback_data="tz_12"),
        ]
    ])
    
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Для начала выберите ваш часовой пояс:",
        reply_markup=keyboard
    )
    await state.set_state(StudentRegistration.waiting_for_timezone)

@router.callback_query(F.data.startswith("tz_"), StudentRegistration.waiting_for_timezone)
async def process_timezone(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора часового пояса"""
    timezone_offset = int(callback.data.split("_")[1])
    
    user_id = callback.from_user.id
    name = callback.from_user.full_name
    username = callback.from_user.username or ""
    
    await db.add_student(user_id, name, username, timezone_offset)
    
    # Определяем текст часового пояса
    msk_diff = timezone_offset - 3
    if msk_diff == 0:
        tz_text = "МСК"
    elif msk_diff > 0:
        tz_text = f"МСК+{msk_diff}"
    else:
        tz_text = f"МСК{msk_diff}"
    
    await callback.message.edit_text(
        f"✅ Регистрация завершена!\n\n"
        f"Ваш часовой пояс: {tz_text}\n\n"
        f"Теперь вы будете получать напоминания об уроках."
    )
    
    await state.clear()
    await show_student_menu(callback.message)

# === МЕНЮ АДМИНА ===

async def show_admin_menu(message: Message):
    """Показать меню админа"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание на сегодня")]
        ],
        resize_keyboard=True
    )
    
    # Получаем URL сайта из переменной окружения
    web_url = os.getenv('WEB_URL', 'http://localhost:8000')
    
    await message.answer(
        "👨‍💼 Панель администратора\n\n"
        f"Управление расписанием и учениками доступно на сайте:\n"
        f"{web_url}",
        reply_markup=keyboard
    )

@router.message(F.text == "📅 Расписание на сегодня")
async def show_today_schedule_admin(message: Message):
    """Показать расписание на сегодня для админа"""
    if message.from_user.id != ADMIN_ID:
        return
    
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    
    admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
    now = datetime.now(admin_tz)
    
    day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][now.weekday()]
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    today_lessons = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == day_name:
                student = students.get(user_id)
                if student:
                    today_lessons.append({
                        'time': lesson['time'],
                        'student': student
                    })
    
    today_lessons.sort(key=lambda x: x['time'])
    
    if not today_lessons:
        await message.answer(
            f"📅 {day_names_ru[day_name]} {now.strftime('%d.%m.%Y')}\n\n"
            f"Сегодня уроков нет 😊"
        )
    else:
        text = f"📅 {day_names_ru[day_name]} {now.strftime('%d.%m.%Y')}\n\n"
        text += f"Уроков: {len(today_lessons)}\n\n"
        
        for lesson in today_lessons:
            name = lesson['student'].get('name', 'Без имени')
            username = lesson['student'].get('username', '')
            username_str = f"@{username}" if username else ""
            text += f"⏰ {lesson['time']} - {name} {username_str}\n"
        
        await message.answer(text)

# === МЕНЮ УЧЕНИКА ===

async def show_student_menu(message: Message):
    """Показать меню ученика"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Мои уроки")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "👋 Главное меню",
        reply_markup=keyboard
    )

@router.message(F.text == "📚 Мои уроки")
async def show_student_lessons(message: Message):
    """Показать уроки ученика"""
    user_id = message.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        await message.answer("❌ Вы не зарегистрированы. Напишите /start")
        return
    
    schedule = await db.get_student_schedule(user_id)
    
    if not schedule:
        await message.answer("📚 У вас пока нет уроков в расписании.")
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
    
    text = "📚 Ваши уроки:\n\n"
    
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    for day in days_order:
        if day in schedule_by_day:
            text += f"📌 {day_names_ru[day]}\n"
            for time in sorted(schedule_by_day[day]):
                # Конвертируем время
                hour, minute = map(int, time.split(':'))
                time_diff = user_tz_offset - admin_tz_offset
                user_hour = (hour + time_diff) % 24
                user_time = f"{user_hour:02d}:{minute:02d}"
                
                text += f"   ⏰ {user_time}\n"
            text += "\n"
    
    await message.answer(text)

# === ОБРАБОТКА ОТВЕТОВ ПО ДЗ ===

@router.callback_query(F.data.startswith("hw_done_"))
async def process_homework_done(callback: CallbackQuery):
    """Ученик сделал ДЗ"""
    parts = callback.data.split("_")
    date = parts[2]
    time = parts[3]
    user_id = callback.from_user.id
    
    await db.save_homework_response(date, time, user_id, "done")
    
    # Отправляем уведомление на сервер
    student = await db.get_student(user_id)
    if student:
        await send_notification_to_server(
            user_id=user_id,
            student_name=student['name'],
            lesson_date=date,
            lesson_time=time,
            status="done"
        )
    
    await callback.message.edit_text("✅ Отлично! Домашнее задание выполнено.")
    await callback.answer()

@router.callback_query(F.data.startswith("hw_not_done_"))
async def process_homework_not_done(callback: CallbackQuery, state: FSMContext):
    """Ученик не сделал ДЗ"""
    parts = callback.data.split("_")
    date = parts[3]
    time = parts[4]
    
    await state.update_data(lesson_date=date, lesson_time=time)
    await state.set_state(HomeworkReason.waiting_for_reason)
    
    await callback.message.edit_text("Напишите причину, почему домашнее задание не выполнено:")
    await callback.answer()

@router.message(HomeworkReason.waiting_for_reason)
async def process_homework_reason(message: Message, state: FSMContext):
    """Получение причины невыполнения ДЗ"""
    reason = message.text
    data = await state.get_data()
    date = data['lesson_date']
    time = data['lesson_time']
    user_id = message.from_user.id
    
    await db.save_homework_response(date, time, user_id, "not_done", reason)
    
    # Отправляем уведомление на сервер
    student = await db.get_student(user_id)
    if student:
        await send_notification_to_server(
            user_id=user_id,
            student_name=student['name'],
            lesson_date=date,
            lesson_time=time,
            status="not_done",
            reason=reason
        )
    
    await message.answer("✅ Спасибо, информация сохранена.")
    await state.clear()

# === ОТПРАВКА УВЕДОМЛЕНИЙ НА СЕРВЕР ===

async def send_notification_to_server(user_id: int, student_name: str, lesson_date: str, lesson_time: str, status: str, reason: str = None):
    """Отправить уведомление на веб-сервер"""
    import aiohttp
    
    try:
        notification_data = {
            'user_id': user_id,
            'student_name': student_name,
            'lesson_date': lesson_date,
            'lesson_time': lesson_time,
            'status': status,
            'reason': reason
        }
        
        # Получаем URL сервера из переменной окружения или используем localhost
        server_url = os.getenv('WEB_SERVER_URL', 'http://localhost:8000')
        
        # Отправляем на веб-сервер
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f'{server_url}/api/notifications/new',
                    json=notification_data,
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Уведомление отправлено на сервер для {student_name}")
            except Exception as e:
                logger.warning(f"Не удалось отправить на сервер: {e}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")

# === ЗАПУСК БОТА ===

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
