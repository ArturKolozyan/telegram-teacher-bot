import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db

router = Router()

# FSM состояния
class StudentRegistration(StatesGroup):
    waiting_for_timezone = State()

class HomeworkReason(StatesGroup):
    waiting_for_reason = State()
    lesson_date = State()
    lesson_time = State()

class ScheduleManagement(StatesGroup):
    selecting_student = State()
    selecting_day = State()
    selecting_time = State()
    custom_time = State()

# === Команды для всех ===

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    # Получаем admin_id из workflow_data
    admin_id = message.bot['admin_id']
    
    # Проверяем, админ ли это
    if user_id == admin_id:
        await show_admin_menu(message)
        return
    
    # Проверяем, зарегистрирован ли ученик
    student = await db.get_student(user_id)
    
    if student:
        await show_student_menu(message)
    else:
        # Регистрация нового ученика
        await message.answer(
            "👋 Привет! Я бот-помощник для учеников.\n\n"
            "Укажи свой часовой пояс:"
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
            ],
            [
                InlineKeyboardButton(text="UTC+7", callback_data="tz_7"),
                InlineKeyboardButton(text="UTC+8", callback_data="tz_8"),
                InlineKeyboardButton(text="UTC+9", callback_data="tz_9")
            ]
        ])
        
        await message.answer(
            "Это нужно для правильного времени уроков и напоминаний.",
            reply_markup=keyboard
        )
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
    
    await message.answer(
        "Главное меню:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "student_schedule")
async def show_student_schedule(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        await callback.answer("Ошибка: ты не зарегистрирован")
        return
    
    schedule = await db.get_student_schedule(user_id)
    
    if not schedule:
        await callback.message.edit_text("У тебя пока нет уроков в расписании.")
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
            message_text += f"{day_names_ru[day]}\n"
            for time in sorted(schedule_by_day[day]):
                # Конвертируем время
                hour, minute = map(int, time.split(':'))
                time_diff = user_tz_offset - admin_tz_offset
                user_hour = (hour + time_diff) % 24
                user_time = f"{user_hour:02d}:{minute:02d}"
                
                message_text += f"⏰ {user_time}\n"
            message_text += "\n"
    
    await callback.message.edit_text(message_text)

# === Обработка ответов по ДЗ ===

@router.callback_query(F.data.startswith("hw_done_"))
async def process_homework_done(callback: CallbackQuery):
    parts = callback.data.split("_")
    date = parts[2]
    time = parts[3]
    user_id = callback.from_user.id
    
    await db.save_homework_response(date, time, user_id, "done")
    
    await callback.message.edit_text(
        "✅ Отлично! Домашнее задание выполнено."
    )
    await callback.answer()

@router.callback_query(F.data.startswith("hw_not_done_"))
async def process_homework_not_done(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    date = parts[3]
    time = parts[4]
    
    await state.update_data(lesson_date=date, lesson_time=time)
    await state.set_state(HomeworkReason.waiting_for_reason)
    
    await callback.message.edit_text(
        "Напиши причину, почему домашнее задание не выполнено:"
    )
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

# === Меню админа ===

async def show_admin_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_today"),
            InlineKeyboardButton(text="📆 Неделя", callback_data="admin_week")
        ],
        [
            InlineKeyboardButton(text="👥 Ученики", callback_data="admin_students"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        ]
    ])
    
    await message.answer(
        "Панель администратора:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    await callback.message.delete()
    await show_admin_menu(callback.message)

# === Просмотр расписания админом ===

@router.callback_query(F.data == "admin_today")
async def show_admin_today(callback: CallbackQuery):
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    
    import pytz
    admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
    now = datetime.now(admin_tz)
    
    day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][now.weekday()]
    
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
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    if not today_lessons:
        message_text = f"📅 Сегодня - {day_names_ru[day_name]} {now.strftime('%d.%m')}\n\nУроков нет."
    else:
        message_text = f"📅 Сегодня - {day_names_ru[day_name]} {now.strftime('%d.%m')}\n"
        message_text += f"У вас {len(today_lessons)} {'урок' if len(today_lessons) == 1 else 'уроков'}:\n\n"
        
        for lesson in today_lessons:
            name = lesson['student'].get('name', 'Без имени')
            username = lesson['student'].get('username', '')
            username_str = f"(@{username})" if username else ""
            message_text += f"├ {lesson['time']} - {name} {username_str}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_week")
async def show_admin_week(callback: CallbackQuery):
    await callback.message.edit_text("📆 Расписание на неделю (в разработке)")
    # TODO: Реализовать полное расписание с кнопками управления

# === Управление учениками ===

@router.callback_query(F.data == "admin_students")
async def show_students_list(callback: CallbackQuery):
    students = await db.get_students()
    schedule = await db.get_schedule()
    
    if not students:
        await callback.message.edit_text("Пока нет зарегистрированных учеников.")
        return
    
    message_text = "👥 Список учеников:\n\n"
    
    keyboard_buttons = []
    
    for user_id, student in students.items():
        name = student.get('name', 'Без имени')
        username = student.get('username', '')
        username_str = f"@{username}" if username else ""
        
        user_schedule = schedule.get(user_id, [])
        lessons_count = len(user_schedule)
        
        if lessons_count > 0:
            message_text += f"✅ {name} ({username_str}) - {lessons_count} {'урок' if lessons_count == 1 else 'уроков'}/нед\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{name} - Изменить",
                callback_data=f"edit_schedule_{user_id}"
            )])
        else:
            message_text += f"🆕 {name} ({username_str}) - без расписания\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{name} - Назначить",
                callback_data=f"add_schedule_{user_id}"
            )])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("add_schedule_"))
async def start_add_schedule(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[2]
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(ScheduleManagement.selecting_day)
    
    student = await db.get_student(int(user_id))
    name = student.get('name', 'Ученик')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Пн", callback_data="day_monday"),
            InlineKeyboardButton(text="Вт", callback_data="day_tuesday"),
            InlineKeyboardButton(text="Ср", callback_data="day_wednesday")
        ],
        [
            InlineKeyboardButton(text="Чт", callback_data="day_thursday"),
            InlineKeyboardButton(text="Пт", callback_data="day_friday"),
            InlineKeyboardButton(text="Сб", callback_data="day_saturday")
        ],
        [InlineKeyboardButton(text="Вс", callback_data="day_sunday")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_schedule")]
    ])
    
    await callback.message.edit_text(
        f"Настройка расписания для {name}\n\nВыбери день недели:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("day_"), ScheduleManagement.selecting_day)
async def process_day_selection(callback: CallbackQuery, state: FSMContext):
    day = callback.data.split("_")[1]
    
    await state.update_data(selected_day=day)
    await state.set_state(ScheduleManagement.selecting_time)
    
    # Получаем занятые времена в этот день
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    occupied_times = {}
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == day:
                time = lesson['time']
                if time not in occupied_times:
                    occupied_times[time] = []
                student = students.get(user_id)
                if student:
                    occupied_times[time].append(student.get('name', 'Без имени'))
    
    # Показываем доступное время
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    message_text = f"{day_names_ru[day]} - доступное время:\n\n"
    
    time_slots = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', 
                  '16:00', '17:00', '18:00', '19:00', '20:00', '21:00']
    
    keyboard_buttons = []
    row = []
    
    for time in time_slots:
        if time in occupied_times:
            message_text += f"❌ {time} - занято ({', '.join(occupied_times[time])})\n"
            row.append(InlineKeyboardButton(text=f"❌ {time}", callback_data=f"time_{time}_occupied"))
        else:
            message_text += f"✅ {time} - свободно\n"
            row.append(InlineKeyboardButton(text=f"✅ {time}", callback_data=f"time_{time}_free"))
        
        if len(row) == 3:
            keyboard_buttons.append(row)
            row = []
    
    if row:
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свое время", callback_data="time_custom")])
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_schedule")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("time_"), ScheduleManagement.selecting_time)
async def process_time_selection(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    
    if parts[1] == "custom":
        await callback.message.edit_text("Введи время в формате ЧЧ:ММ (например, 15:30):")
        await state.set_state(ScheduleManagement.custom_time)
        return
    
    time = parts[1]
    status = parts[2]
    
    data = await state.get_data()
    target_user_id = int(data['target_user_id'])
    selected_day = data['selected_day']
    
    if status == "occupied":
        # Предупреждение о групповом занятии
        schedule = await db.get_schedule()
        students = await db.get_students()
        
        occupied_students = []
        for user_id, user_schedule in schedule.items():
            for lesson in user_schedule:
                if lesson['day'] == selected_day and lesson['time'] == time:
                    student = students.get(user_id)
                    if student:
                        occupied_students.append(student.get('name', 'Без имени'))
        
        student = await db.get_student(target_user_id)
        student_name = student.get('name', 'Ученик')
        
        day_names_ru = {
            'monday': 'понедельник',
            'tuesday': 'вторник',
            'wednesday': 'среду',
            'thursday': 'четверг',
            'friday': 'пятницу',
            'saturday': 'субботу',
            'sunday': 'воскресенье'
        }
        
        message = f"❌ Внимание!\n\nВ {day_names_ru[selected_day]} {time} уже назначен урок:\n"
        for name in occupied_students:
            message += f"• {name}\n"
        message += f"\nХочешь добавить {student_name} в это же время?\n(Будет групповое занятие)"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, групповое", callback_data=f"confirm_group_{time}"),
                InlineKeyboardButton(text="❌ Выбрать другое", callback_data=f"day_{selected_day}")
            ]
        ])
        
        await callback.message.edit_text(message, reply_markup=keyboard)
        return
    
    # Добавляем урок
    await db.add_lesson_to_schedule(target_user_id, selected_day, time)
    
    student = await db.get_student(target_user_id)
    student_name = student.get('name', 'Ученик')
    
    await callback.message.edit_text(
        f"✅ Урок добавлен!\n\n{student_name} - {selected_day} {time}"
    )
    
    await state.clear()

@router.callback_query(F.data.startswith("confirm_group_"), ScheduleManagement.selecting_time)
async def confirm_group_lesson(callback: CallbackQuery, state: FSMContext):
    time = callback.data.split("_")[2]
    
    data = await state.get_data()
    target_user_id = int(data['target_user_id'])
    selected_day = data['selected_day']
    
    await db.add_lesson_to_schedule(target_user_id, selected_day, time)
    
    student = await db.get_student(target_user_id)
    student_name = student.get('name', 'Ученик')
    
    await callback.message.edit_text(
        f"✅ Групповое занятие создано!\n\n{student_name} добавлен в {selected_day} {time}"
    )
    
    await state.clear()

@router.message(ScheduleManagement.custom_time)
async def process_custom_time(message: Message, state: FSMContext):
    time = message.text.strip()
    
    # Простая валидация
    if not time or ':' not in time:
        await message.answer("Неверный формат. Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    data = await state.get_data()
    target_user_id = int(data['target_user_id'])
    selected_day = data['selected_day']
    
    await db.add_lesson_to_schedule(target_user_id, selected_day, time)
    
    student = await db.get_student(target_user_id)
    student_name = student.get('name', 'Ученик')
    
    await message.answer(
        f"✅ Урок добавлен!\n\n{student_name} - {selected_day} {time}"
    )
    
    await state.clear()

@router.callback_query(F.data == "cancel_schedule")
async def cancel_schedule_management(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await show_admin_menu(callback.message)

# === Настройки админа ===

@router.callback_query(F.data == "admin_settings")
async def show_admin_settings(callback: CallbackQuery):
    settings = await db.get_settings()
    
    message_text = "⚙️ Настройки\n\n"
    message_text += f"Твой часовой пояс: UTC+{settings['admin_timezone']} (МСК)\n\n"
    message_text += f"Напоминания ученикам:\n⏰ За сколько до урока: {settings['reminder_hours_before']} {'час' if settings['reminder_hours_before'] == 1 else 'часов'}\n\n"
    message_text += f"Отчеты по ДЗ:\n📊 Когда отправлять: За {settings['homework_check_minutes_before']} минут до урока\n\n"
    message_text += f"Мое напоминание о расписании:\n🔔 Время отправки: {settings['admin_daily_reminder_time']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
