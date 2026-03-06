"""
Telegram бот для учеников и репетиторов
Профессиональная версия с четкой структурой и понятными сообщениями
"""
import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import pytz

import database as db
import scheduler as sched
import simple_auth

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

# ============================================================================
# КОМАНДА /start - ГЛАВНАЯ ТОЧКА ВХОДА
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    """Обработка команды /start для всех пользователей"""
    user_id = message.from_user.id
    args = command.args if command.args else None
    
    # 1. ПРИВЯЗКА TELEGRAM РЕПЕТИТОРА
    if args and args.startswith('BIND_'):
        bind_token = args[5:]
        await handle_tutor_bind(message, bind_token)
        return
    
    # 2. ПРОВЕРКА - РЕПЕТИТОР ИЛИ УЧЕНИК?
    tutor = simple_auth.get_tutor_by_telegram_id(user_id)
    
    if tutor:
        # Это репетитор
        await show_tutor_welcome(message, tutor)
        return
    
    # 3. ПРОВЕРКА - УЧЕНИК УЖЕ ЗАРЕГИСТРИРОВАН?
    student = await db.get_student(user_id)
    
    if student:
        # Ученик уже зарегистрирован
        await show_student_welcome(message, student)
        return
    
    # 4. НОВЫЙ УЧЕНИК - РЕГИСТРАЦИЯ
    tutor_id = args if args else None
    
    if not tutor_id:
        # Нет ссылки от репетитора
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Для регистрации вам нужна специальная ссылка от вашего репетитора.\n\n"
            "📌 Попросите репетитора отправить вам ссылку-приглашение.",
            parse_mode="HTML"
        )
        return
    
    # Начинаем регистрацию
    await state.update_data(tutor_id=tutor_id)
    await start_student_registration(message, state, tutor_id)

# ============================================================================
# ПРИВЯЗКА TELEGRAM РЕПЕТИТОРА
# ============================================================================

async def handle_tutor_bind(message: Message, bind_token: str):
    """Привязка Telegram аккаунта репетитора"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    result = simple_auth.bind_telegram(bind_token, user_id, username)
    
    if result['success']:
        tutor_info = result['tutor_info']
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📅 Мои уроки на сегодня")],
                [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Мои ученики")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"✅ <b>Telegram успешно привязан!</b>\n\n"
            f"👤 <b>Репетитор:</b> {tutor_info['name']}\n"
            f"📧 <b>Email:</b> {tutor_info['email']}\n\n"
            f"Теперь вы будете получать уведомления об уроках в этом чате.\n\n"
            f"💡 <b>Управление системой:</b>\n"
            f"Добавляйте учеников, создавайте расписание и отмечайте уроки на сайте.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ <b>Ошибка привязки</b>\n\n"
            f"{result['message']}\n\n"
            f"Возможно, ссылка устарела или уже была использована.\n"
            f"Получите новую ссылку в настройках на сайте.",
            parse_mode="HTML"
        )

# ============================================================================
# ПРИВЕТСТВИЕ РЕПЕТИТОРА
# ============================================================================

async def show_tutor_welcome(message: Message, tutor: dict):
    """Показать приветствие для репетитора"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Мои уроки на сегодня")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Мои ученики")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"👋 <b>Добро пожаловать, {tutor['name']}!</b>\n\n"
        f"Используйте кнопки ниже для быстрого доступа к информации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ============================================================================
# ПРИВЕТСТВИЕ УЧЕНИКА
# ============================================================================

async def show_student_welcome(message: Message, student: dict):
    """Показать приветствие для ученика"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Мое расписание")],
            [KeyboardButton(text="ℹ️ Информация")]
        ],
        resize_keyboard=True
    )
    
    name = student.get('name', 'Ученик')
    first_name = name.split()[0] if name else 'Ученик'
    
    await message.answer(
        f"👋 <b>Привет, {first_name}!</b>\n\n"
        f"Используйте кнопки ниже:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ============================================================================
# РЕГИСТРАЦИЯ УЧЕНИКА
# ============================================================================

async def start_student_registration(message: Message, state: FSMContext, tutor_id: str):
    """Начать регистрацию ученика"""
    # Получаем информацию о репетиторе
    tutor_info = simple_auth.get_tutor_info()
    tutor_name = tutor_info['name'] if tutor_info else "вашего репетитора"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 UTC -12, Веллингтон", callback_data="tz_-12")],
        [InlineKeyboardButton(text="🌍 UTC -11, Острова Мидуэй", callback_data="tz_-11")],
        [InlineKeyboardButton(text="🌍 UTC -10, Гонолулу", callback_data="tz_-10")],
        [InlineKeyboardButton(text="🌍 UTC -9, Анкоридж", callback_data="tz_-9")],
        [InlineKeyboardButton(text="🌍 UTC -8, Лос-Анджелес", callback_data="tz_-8")],
        [InlineKeyboardButton(text="🌍 UTC -7, Денвер", callback_data="tz_-7")],
        [InlineKeyboardButton(text="🌍 UTC -6, Чикаго", callback_data="tz_-6")],
        [InlineKeyboardButton(text="🌍 UTC -5, Нью-Йорк", callback_data="tz_-5")],
        [InlineKeyboardButton(text="🌍 UTC -4, Санто-Доминго", callback_data="tz_-4")],
        [InlineKeyboardButton(text="🌍 UTC -3, Рио-Де-Жанейро", callback_data="tz_-3")],
        [InlineKeyboardButton(text="🌍 UTC -2, Гренландия", callback_data="tz_-2")],
        [InlineKeyboardButton(text="🌍 UTC -1, Азорские Острова", callback_data="tz_-1")],
        [InlineKeyboardButton(text="🇬🇧 UTC +0, Лондон", callback_data="tz_0")],
        [InlineKeyboardButton(text="🇫🇷 UTC +1, Париж, Кишинев", callback_data="tz_1")],
        [InlineKeyboardButton(text="🇺🇦 UTC +2, Киев, Калининград", callback_data="tz_2")],
        [InlineKeyboardButton(text="🇷🇺 UTC +3, Москва, Минск", callback_data="tz_3")],
        [InlineKeyboardButton(text="🇦🇲 UTC +4, Самара, Баку, Ереван", callback_data="tz_4")],
        [InlineKeyboardButton(text="🇹🇯 UTC +5, Душанбе, Екатеринбург", callback_data="tz_5")],
        [InlineKeyboardButton(text="🇰🇿 UTC +6, Бишкек, Астана, Омск", callback_data="tz_6")],
        [InlineKeyboardButton(text="🇷🇺 UTC +7, Красноярск", callback_data="tz_7")],
        [InlineKeyboardButton(text="🇨🇳 UTC +8, Иркутск, Пекин", callback_data="tz_8")],
        [InlineKeyboardButton(text="🇯🇵 UTC +9, Якутск, Токио", callback_data="tz_9")],
        [InlineKeyboardButton(text="🇷🇺 UTC +10, Владивосток", callback_data="tz_10")],
        [InlineKeyboardButton(text="🇷🇺 UTC +11, Среднеколымск", callback_data="tz_11")],
        [InlineKeyboardButton(text="🇷🇺 UTC +12, Камчатка", callback_data="tz_12")]
    ])
    
    await message.answer(
        f"📝 <b>Регистрация</b>\n\n"
        f"Вы регистрируетесь у репетитора:\n"
        f"👤 <b>{tutor_name}</b>\n\n"
        f"🌍 <b>Выберите ваш часовой пояс:</b>\n"
        f"Это нужно для правильного времени уведомлений об уроках.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(StudentRegistration.waiting_for_timezone)

@router.callback_query(F.data.startswith("tz_"), StudentRegistration.waiting_for_timezone)
async def process_timezone_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора часового пояса"""
    timezone_offset = int(callback.data.split("_")[1])
    
    user_id = callback.from_user.id
    name = callback.from_user.full_name
    username = callback.from_user.username or ""
    
    # Получаем tutor_id из состояния
    data = await state.get_data()
    tutor_id = data.get('tutor_id')
    
    if not tutor_id:
        await callback.message.edit_text(
            "❌ <b>Ошибка регистрации</b>\n\n"
            "Не указан репетитор. Попросите репетитора отправить вам новую ссылку.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Регистрируем ученика
    await db.add_student(user_id, name, username, timezone_offset, tutor_id)
    
    # Определяем текст часового пояса
    msk_diff = timezone_offset - 3
    if msk_diff == 0:
        tz_text = "МСК (UTC+3)"
    elif msk_diff > 0:
        tz_text = f"МСК+{msk_diff} (UTC+{timezone_offset})"
    else:
        tz_text = f"МСК{msk_diff} (UTC+{timezone_offset})"
    
    # Создаем клавиатуру для ученика
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Мое расписание")],
            [KeyboardButton(text="ℹ️ Информация")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.edit_text(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"🌍 <b>Часовой пояс:</b> {tz_text}\n\n"
        f"Теперь вы будете получать напоминания об уроках в удобное для вас время.",
        parse_mode="HTML"
    )
    
    # Отправляем приветственное сообщение с клавиатурой
    first_name = name.split()[0] if name else 'Ученик'
    await callback.message.answer(
        f"👋 <b>Привет, {first_name}!</b>\n\n"
        f"Используйте кнопки ниже для навигации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.clear()

# ============================================================================
# КНОПКИ РЕПЕТИТОРА
# ============================================================================

@router.message(F.text == "📅 Мои уроки на сегодня")
async def show_tutor_today_lessons(message: Message):
    """Показать уроки репетитора на сегодня"""
    user_id = message.from_user.id
    
    # Проверяем - это репетитор?
    tutor = simple_auth.get_tutor_by_telegram_id(user_id)
    if not tutor:
        return
    
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    
    admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
    now = datetime.now(admin_tz)
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][now.weekday()]
    
    # Получаем уроки из новой системы (lessons.json)
    import lessons as lessons_db
    
    # Формируем дату в формате YYYY-MM-DD
    today_date = now.strftime('%Y-%m-%d')
    
    # Получаем все уроки на сегодня
    all_lessons = await lessons_db.get_lessons_by_date(today_date)
    
    # Получаем учеников репетитора
    tutor_id = tutor['tutor_id']
    students = await db.get_students_by_tutor(tutor_id)
    
    # Фильтруем уроки только этого репетитора
    today_lessons = []
    for lesson in all_lessons:
        student_id = str(lesson['student_id'])
        if student_id in students:
            student = students[student_id]
            today_lessons.append({
                'time': lesson['time'],
                'student': student,
                'completed': lesson.get('completed', False),
                'is_moved': lesson.get('is_moved', False)
            })
    
    today_lessons.sort(key=lambda x: x['time'])
    
    if not today_lessons:
        await message.answer(
            f"📅 <b>{day_names_ru[day_name]}, {now.strftime('%d.%m.%Y')}</b>\n\n"
            f"🎉 Сегодня уроков нет!\n\n"
            f"Отличный день для отдыха или подготовки к следующим занятиям.",
            parse_mode="HTML"
        )
    else:
        text = f"📅 <b>{day_names_ru[day_name]}, {now.strftime('%d.%m.%Y')}</b>\n\n"
        text += f"📚 <b>Уроков сегодня:</b> {len(today_lessons)}\n\n"
        
        for i, lesson in enumerate(today_lessons, 1):
            name = lesson['student'].get('name', 'Без имени')
            username = lesson['student'].get('username', '')
            username_str = f" (@{username})" if username else ""
            
            # Добавляем статус урока
            status = ""
            if lesson['completed']:
                status = " ✅"
            elif lesson['is_moved']:
                status = " 🔄"
            
            text += f"{i}. ⏰ <b>{lesson['time']}</b> — {name}{username_str}{status}\n"
        
        text += f"\n💡 Управляйте уроками на сайте"
        
        await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📊 Статистика")
async def show_tutor_stats(message: Message):
    """Показать статистику репетитора"""
    user_id = message.from_user.id
    
    # Проверяем - это репетитор?
    tutor = simple_auth.get_tutor_by_telegram_id(user_id)
    if not tutor:
        return
    
    tutor_id = tutor['tutor_id']
    students = await db.get_students_by_tutor(tutor_id)
    
    if not students:
        await message.answer(
            f"📊 <b>Ваша статистика</b>\n\n"
            f"👥 <b>Учеников:</b> 0\n"
            f"📚 <b>Уроков:</b> 0\n\n"
            f"📌 Начните с добавления учеников через сайт!",
            parse_mode="HTML"
        )
        return
    
    # Считаем уроки из новой системы (lessons.json)
    import lessons as lessons_db
    
    # Получаем все уроки
    all_lessons_data = await lessons_db.load_lessons()
    
    # Считаем уроки этого репетитора
    total_lessons = 0
    completed_lessons = 0
    
    for lesson in all_lessons_data.values():
        student_id = str(lesson['student_id'])
        if student_id in students:
            total_lessons += 1
            if lesson.get('completed', False):
                completed_lessons += 1
    
    await message.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👥 <b>Учеников:</b> {len(students)}\n"
        f"📚 <b>Всего уроков:</b> {total_lessons}\n"
        f"✅ <b>Проведено:</b> {completed_lessons}\n"
        f"⏳ <b>Запланировано:</b> {total_lessons - completed_lessons}\n\n"
        f"💡 Подробная статистика и доходы доступны на сайте",
        parse_mode="HTML"
    )

@router.message(F.text == "👥 Мои ученики")
async def show_tutor_students(message: Message):
    """Показать список учеников репетитора"""
    user_id = message.from_user.id
    
    # Проверяем - это репетитор?
    tutor = simple_auth.get_tutor_by_telegram_id(user_id)
    if not tutor:
        return
    
    tutor_id = tutor['tutor_id']
    students = await db.get_students_by_tutor(tutor_id)
    
    if not students:
        await message.answer(
            f"👥 <b>Мои ученики</b>\n\n"
            f"У вас пока нет учеников.\n\n"
            f"📌 Отправьте ученикам ссылку-приглашение из настроек на сайте.",
            parse_mode="HTML"
        )
        return
    
    # Получаем уроки из новой системы
    import lessons as lessons_db
    all_lessons_data = await lessons_db.load_lessons()
    
    text = f"👥 <b>Мои ученики ({len(students)})</b>\n\n"
    
    for i, (user_id_str, student) in enumerate(students.items(), 1):
        name = student.get('name', 'Без имени')
        username = student.get('username', '')
        username_str = f" (@{username})" if username else ""
        
        # Считаем уроки ученика из новой системы
        lessons_count = 0
        for lesson in all_lessons_data.values():
            if str(lesson['student_id']) == user_id_str:
                lessons_count += 1
        
        text += f"{i}. {name}{username_str}\n"
        if lessons_count > 0:
            text += f"   📚 Уроков: {lessons_count}\n\n"
        else:
            text += f"   📚 Уроков пока нет\n\n"
    
    text += f"💡 Управляйте учениками на сайте"
    
    await message.answer(text, parse_mode="HTML")

# ============================================================================
# КНОПКИ УЧЕНИКА
# ============================================================================

@router.message(F.text == "📚 Мое расписание")
async def show_student_schedule(message: Message):
    """Показать расписание ученика"""
    user_id = message.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        await message.answer(
            "❌ <b>Вы не зарегистрированы</b>\n\n"
            "Нажмите /start для регистрации.",
            parse_mode="HTML"
        )
        return
    
    # Получаем уроки ученика из новой системы
    import lessons as lessons_db
    from datetime import datetime, timedelta
    
    all_lessons_data = await lessons_db.load_lessons()
    
    # Фильтруем уроки этого ученика (только будущие и сегодняшние)
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    user_tz_offset = student['timezone_offset']
    
    import pytz
    admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
    now = datetime.now(admin_tz)
    today_date = now.strftime('%Y-%m-%d')
    
    student_lessons = []
    for lesson in all_lessons_data.values():
        if lesson['student_id'] == user_id and lesson['date'] >= today_date:
            student_lessons.append(lesson)
    
    if not student_lessons:
        await message.answer(
            "📚 <b>Мое расписание</b>\n\n"
            "У вас пока нет запланированных уроков.\n\n"
            "📌 Ваш репетитор добавит уроки, и вы получите уведомления.",
            parse_mode="HTML"
        )
        return
    
    # Сортируем по дате и времени
    student_lessons.sort(key=lambda x: (x['date'], x['time']))
    
    # Показываем ближайшие 10 уроков
    text = "📚 <b>Мое расписание</b>\n\n"
    text += f"Ближайшие уроки:\n\n"
    
    day_names_ru = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }
    
    for i, lesson in enumerate(student_lessons[:10], 1):
        # Парсим дату
        lesson_date = datetime.strptime(lesson['date'], '%Y-%m-%d')
        day_name = day_names_ru[lesson_date.weekday()]
        date_str = lesson_date.strftime('%d.%m.%Y')
        
        # Конвертируем время в часовой пояс ученика
        hour, minute = map(int, lesson['time'].split(':'))
        time_diff = user_tz_offset - admin_tz_offset
        user_hour = (hour + time_diff) % 24
        user_time = f"{user_hour:02d}:{minute:02d}"
        
        # Статус
        status = ""
        if lesson.get('completed'):
            status = " ✅"
        elif lesson.get('is_moved'):
            status = " 🔄"
        
        text += f"{i}. <b>{day_name}, {date_str}</b>\n"
        text += f"   ⏰ {user_time}{status}\n\n"
    
    if len(student_lessons) > 10:
        text += f"... и еще {len(student_lessons) - 10} уроков\n\n"
    
    text += "💡 Вы будете получать напоминания перед каждым уроком"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "ℹ️ Информация")
async def show_student_info(message: Message):
    """Показать информацию для ученика"""
    user_id = message.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        return
    
    name = student.get('name', 'Ученик')
    tz_offset = student.get('timezone_offset', 3)
    
    # Определяем текст часового пояса
    msk_diff = tz_offset - 3
    if msk_diff == 0:
        tz_text = "МСК (UTC+3)"
    elif msk_diff > 0:
        tz_text = f"МСК+{msk_diff} (UTC+{tz_offset})"
    else:
        tz_text = f"МСК{msk_diff} (UTC+{tz_offset})"
    
    await message.answer(
        f"ℹ️ <b>Ваша информация</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"🌍 <b>Часовой пояс:</b> {tz_text}\n\n"
        f"📚 <b>Что я умею:</b>\n"
        f"• Показывать ваше расписание\n"
        f"• Напоминать о предстоящих уроках\n"
        f"• Спрашивать о выполнении домашнего задания\n\n"
        f"💡 Если нужна помощь, обратитесь к вашему репетитору",
        parse_mode="HTML"
    )

# ============================================================================
# ОБРАБОТКА ОТВЕТОВ ПО ДОМАШНЕМУ ЗАДАНИЮ
# ============================================================================

@router.callback_query(F.data.startswith("hw_done_"))
async def process_homework_done(callback: CallbackQuery):
    """Ученик сделал ДЗ"""
    parts = callback.data.split("_")
    date = parts[2]
    time = parts[3]
    user_id = callback.from_user.id
    
    await db.save_homework_response(date, time, user_id, "done")
    
    await callback.message.edit_text(
        "✅ <b>Отлично!</b>\n\n"
        "Домашнее задание выполнено. Встретимся на уроке! 📚",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("hw_not_done_"))
async def process_homework_not_done(callback: CallbackQuery):
    """Ученик не сделал ДЗ"""
    parts = callback.data.split("_")
    date = parts[3]
    time = parts[4]
    user_id = callback.from_user.id
    
    await db.save_homework_response(date, time, user_id, "not_done")
    
    await callback.message.edit_text(
        "📚 <b>Не беда!</b>\n\n"
        "У тебя еще есть время до урока. Постарайся сделать домашнее задание, "
        "чтобы урок прошел максимально продуктивно! 💪",
        parse_mode="HTML"
    )
    await callback.answer()

# ============================================================================
# ЗАПУСК БОТА
# ============================================================================

async def main():
    """Главная функция запуска бота"""
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
        args=[bot]
    )
    
    # Ежедневное напоминание репетитору
    settings = await db.get_settings()
    reminder_time = settings['admin_daily_reminder_time']
    hour, minute = map(int, reminder_time.split(':'))
    
    scheduler.add_job(
        sched.send_admin_daily_reminder,
        'cron',
        hour=hour,
        minute=minute,
        args=[bot]
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
