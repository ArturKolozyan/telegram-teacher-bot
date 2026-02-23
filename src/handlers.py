import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
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

class SettingsChange(StatesGroup):
    waiting_for_reminder_time = State()
    waiting_for_report_time = State()
    waiting_for_daily_time = State()
    waiting_for_timezone = State()

class LessonManagement(StatesGroup):
    moving_lesson_select_day = State()
    moving_lesson_select_time = State()
    lesson_data = State()

# === Вспомогательные функции ===

def check_time_conflict(new_time: str, existing_times: list) -> tuple:
    """
    Проверяет конфликт времени. Урок длится 1 час.
    Возвращает (has_conflict, conflict_time)
    """
    from datetime import datetime, timedelta
    
    try:
        new_hour, new_minute = map(int, new_time.split(':'))
        new_dt = datetime(2000, 1, 1, new_hour, new_minute)
        new_end = new_dt + timedelta(hours=1)
        
        for existing_time in existing_times:
            ex_hour, ex_minute = map(int, existing_time.split(':'))
            ex_dt = datetime(2000, 1, 1, ex_hour, ex_minute)
            ex_end = ex_dt + timedelta(hours=1)
            
            # Проверяем пересечение интервалов
            if (new_dt < ex_end and new_end > ex_dt):
                return (True, existing_time)
        
        return (False, None)
    except:
        return (False, None)

def get_filtered_time_slots(occupied_times: dict) -> list:
    """
    Возвращает список временных слотов с учетом того, что урок длится час.
    Если урок в 13:30, то скрываем 13:00 и 14:00, показываем 13:30.
    """
    from datetime import datetime, timedelta
    
    standard_slots = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', 
                      '16:00', '17:00', '18:00', '19:00', '20:00', '21:00']
    
    # Собираем все занятые времена
    all_occupied = list(occupied_times.keys())
    
    # Определяем какие стандартные слоты нужно скрыть
    hidden_slots = set()
    custom_times = []
    
    for occupied_time in all_occupied:
        try:
            hour, minute = map(int, occupied_time.split(':'))
            
            # Если это нестандартное время (не круглый час)
            if minute != 0:
                custom_times.append(occupied_time)
                
                # Скрываем слоты которые покрывает этот урок
                dt = datetime(2000, 1, 1, hour, minute)
                end_dt = dt + timedelta(hours=1)
                
                # Скрываем час начала
                start_slot = f"{hour:02d}:00"
                if start_slot in standard_slots:
                    hidden_slots.add(start_slot)
                
                # Скрываем час окончания
                end_slot = f"{end_dt.hour:02d}:00"
                if end_slot in standard_slots:
                    hidden_slots.add(end_slot)
        except:
            pass
    
    # Формируем итоговый список
    result = []
    for slot in standard_slots:
        if slot not in hidden_slots:
            result.append(slot)
    
    # Добавляем кастомные времена
    result.extend(custom_times)
    result.sort()
    
    return result

# === Команда /start ===

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, admin_id: int):
    user_id = message.from_user.id
    
    # Постоянная клавиатура
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Главное меню")]],
        resize_keyboard=True
    )
    
    # Проверяем админ или ученик
    if user_id == admin_id:
        await message.answer("👋 Добро пожаловать, администратор!", reply_markup=reply_keyboard)
        await show_admin_menu(message)
        return
    
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

@router.callback_query(F.data == "student_schedule")
async def show_student_schedule(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    student = await db.get_student(user_id)
    if not student:
        await callback.answer("Ошибка: ты не зарегистрирован")
        return
    
    schedule = await db.get_student_schedule(user_id)
    
    if not schedule:
        await callback.message.edit_text("📅 У тебя пока нет уроков в расписании.")
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
    
    await callback.message.edit_text(message_text)

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
    
    await message.answer("🎓 Панель администратора", reply_markup=keyboard)

@router.message(F.text == "📋 Главное меню")
async def back_to_menu(message: Message, admin_id: int):
    user_id = message.from_user.id
    
    if user_id == admin_id:
        await show_admin_menu(message)
    else:
        await show_student_menu(message)

@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    await callback.message.delete()
    await show_admin_menu(callback.message)

# === Просмотр расписания на сегодня ===

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
        message_text = f"📅 Сегодня - {day_names_ru[day_name]} {now.strftime('%d.%m')}\n\n✨ Уроков нет, отдыхай!"
    else:
        message_text = f"📅 Сегодня - {day_names_ru[day_name]} {now.strftime('%d.%m')}\n\n"
        message_text += f"У тебя {len(today_lessons)} {'урок' if len(today_lessons) == 1 else 'уроков'}:\n\n"
        
        for lesson in today_lessons:
            name = lesson['student'].get('name', 'Без имени')
            username = lesson['student'].get('username', '')
            username_str = f"@{username}" if username else ""
            message_text += f"⏰ {lesson['time']} - {name} {username_str}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

# === Просмотр расписания на неделю ===

@router.callback_query(F.data == "admin_week")
async def show_admin_week(callback: CallbackQuery):
    message_text = "📆 Расписание на неделю\n\nВыбери день недели:"
    
    # Кнопки выбора дня - по одной в ряд для одинакового размера
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="weekday_monday")],
        [InlineKeyboardButton(text="Вторник", callback_data="weekday_tuesday")],
        [InlineKeyboardButton(text="Среда", callback_data="weekday_wednesday")],
        [InlineKeyboardButton(text="Четверг", callback_data="weekday_thursday")],
        [InlineKeyboardButton(text="Пятница", callback_data="weekday_friday")],
        [InlineKeyboardButton(text="Суббота", callback_data="weekday_saturday")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="weekday_sunday")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

# === Просмотр конкретного дня с кнопками управления ===

async def show_day_schedule_after_action(message: Message, day: str):
    """Показать расписание дня после действия (удаление/перенос)"""
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    # Собираем уроки на этот день
    day_lessons = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == day:
                student = students.get(user_id)
                if student:
                    day_lessons.append({
                        'time': lesson['time'],
                        'student': student,
                        'user_id': user_id
                    })
    
    day_lessons.sort(key=lambda x: x['time'])
    
    # Группируем по времени
    time_groups = {}
    for lesson in day_lessons:
        time = lesson['time']
        if time not in time_groups:
            time_groups[time] = []
        time_groups[time].append(lesson)
    
    # Получаем отфильтрованные слоты с учетом того что урок длится час
    all_times = get_filtered_time_slots(time_groups)
    
    message_text = f"📅 {day_names_ru[day]}\n\n"
    
    keyboard_buttons = []
    
    for time in all_times:
        if time in time_groups:
            group = time_groups[time]
            
            if len(group) == 1:
                # Одиночный урок
                lesson = group[0]
                name = lesson['student'].get('name', 'Без имени')
                username = lesson['student'].get('username', '')
                username_str = f"@{username}" if username else ""
                message_text += f"⏰ {time} - {name} {username_str}\n"
                
                # Кнопки управления
                keyboard_buttons.append([
                    InlineKeyboardButton(text=f"🔄 Перенести {time}", callback_data=f"move_{day}_{time}_{lesson['user_id']}"),
                    InlineKeyboardButton(text=f"❌ Удалить {time}", callback_data=f"delete_{day}_{time}_{lesson['user_id']}")
                ])
            else:
                # Групповое занятие
                names = [l['student'].get('name', 'Без имени') for l in group]
                message_text += f"⏰ {time} - {', '.join(names)} (группа)\n"
                
                # Кнопки управления для группы
                user_ids = '_'.join([str(l['user_id']) for l in group])
                keyboard_buttons.append([
                    InlineKeyboardButton(text=f"🔄 Перенести группу {time}", callback_data=f"move_group_{day}_{time}_{user_ids}"),
                    InlineKeyboardButton(text=f"❌ Удалить группу {time}", callback_data=f"delete_group_{day}_{time}_{user_ids}")
                ])
        else:
            # Свободное время
            message_text += f"✅ {time} - \n"
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ К выбору дня", callback_data="admin_week")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("weekday_"))
async def show_day_schedule(callback: CallbackQuery):
    day = callback.data.split("_")[1]
    await show_day_schedule_after_action(callback.message, day)

# === Удаление урока ===

@router.callback_query(F.data.startswith("delete_"))
async def delete_lesson(callback: CallbackQuery):
    parts = callback.data.split("_")
    
    if parts[1] == "group":
        # Удаление группового урока
        day = parts[2]
        time = parts[3]
        user_ids = parts[4].split('_')
        
        for user_id in user_ids:
            await db.remove_lesson_from_schedule(int(user_id), day, time)
        
        await callback.answer("✅ Групповой урок удален")
    else:
        # Удаление одиночного урока
        day = parts[1]
        time = parts[2]
        user_id = int(parts[3])
        
        await db.remove_lesson_from_schedule(user_id, day, time)
        
        await callback.answer("✅ Урок удален")
    
    # Возвращаемся к обновленному расписанию дня
    await show_day_schedule_after_action(callback.message, day)

# === Перенос урока ===

@router.callback_query(F.data.startswith("move_"))
async def start_move_lesson(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    
    if parts[1] == "group":
        # Перенос группового урока
        day = parts[2]
        time = parts[3]
        user_ids = parts[4].split('_')
        
        await state.update_data(
            old_day=day,
            old_time=time,
            user_ids=user_ids,
            is_group=True
        )
    else:
        # Перенос одиночного урока
        day = parts[1]
        time = parts[2]
        user_id = parts[3]
        
        await state.update_data(
            old_day=day,
            old_time=time,
            user_ids=[user_id],
            is_group=False
        )
    
    await state.set_state(LessonManagement.moving_lesson_select_day)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="moveday_monday")],
        [InlineKeyboardButton(text="Вторник", callback_data="moveday_tuesday")],
        [InlineKeyboardButton(text="Среда", callback_data="moveday_wednesday")],
        [InlineKeyboardButton(text="Четверг", callback_data="moveday_thursday")],
        [InlineKeyboardButton(text="Пятница", callback_data="moveday_friday")],
        [InlineKeyboardButton(text="Суббота", callback_data="moveday_saturday")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="moveday_sunday")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_move")]
    ])
    
    await callback.message.edit_text(
        f"🔄 Перенос урока\n\nВыбери новый день недели:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("moveday_"), LessonManagement.moving_lesson_select_day)
async def process_move_day(callback: CallbackQuery, state: FSMContext):
    new_day = callback.data.split("_")[1]
    
    await state.update_data(new_day=new_day)
    await state.set_state(LessonManagement.moving_lesson_select_time)
    
    # Получаем данные о переносимом уроке
    data = await state.get_data()
    old_day = data['old_day']
    old_time = data['old_time']
    
    # Получаем занятые времена на выбранный день
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    occupied_times = {}
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == new_day:
                # Исключаем переносимый урок если переносим в тот же день
                if not (lesson['day'] == old_day and lesson['time'] == old_time):
                    time = lesson['time']
                    if time not in occupied_times:
                        occupied_times[time] = []
                    student = students.get(user_id)
                    if student:
                        occupied_times[time].append(student.get('name', 'Без имени'))
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    message_text = f"🔄 Перенос урока\n\n📅 {day_names_ru[new_day]}\n\nСвободное время:\n\n"
    
    # Получаем отфильтрованные слоты с учетом занятых времен
    filtered_slots = get_filtered_time_slots(occupied_times)
    
    keyboard_buttons = []
    row = []
    
    for time in filtered_slots:
        if time not in occupied_times:
            message_text += f"✅ {time} - \n"
            row.append(InlineKeyboardButton(text=f"{time}", callback_data=f"movetime_{time}"))
            
            if len(row) == 3:
                keyboard_buttons.append(row)
                row = []
    
    if row:
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свое время", callback_data="movetime_custom")])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="move_back_to_days"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_move")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("movetime_"), LessonManagement.moving_lesson_select_time)
async def process_move_time_button(callback: CallbackQuery, state: FSMContext):
    time_part = callback.data.split("_")[1]
    
    if time_part == "custom":
        await callback.message.edit_text("✏️ Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    new_time = time_part
    
    data = await state.get_data()
    old_day = data['old_day']
    old_time = data['old_time']
    new_day = data['new_day']
    user_ids = data['user_ids']
    is_group = data['is_group']
    
    # Удаляем старые уроки и добавляем новые
    for user_id in user_ids:
        await db.remove_lesson_from_schedule(int(user_id), old_day, old_time)
        await db.add_lesson_to_schedule(int(user_id), new_day, new_time)
    
    day_names_ru = {
        'monday': 'Пн',
        'tuesday': 'Вт',
        'wednesday': 'Ср',
        'thursday': 'Чт',
        'friday': 'Пт',
        'saturday': 'Сб',
        'sunday': 'Вс'
    }
    
    if is_group:
        await callback.message.edit_text(f"✅ Групповой урок перенесен!\n\n{day_names_ru[old_day]} {old_time} → {day_names_ru[new_day]} {new_time}")
    else:
        await callback.message.edit_text(f"✅ Урок перенесен!\n\n{day_names_ru[old_day]} {old_time} → {day_names_ru[new_day]} {new_time}")
    
    await state.clear()
    await callback.answer()

@router.message(LessonManagement.moving_lesson_select_time)
async def process_move_time_text(message: Message, state: FSMContext):
    new_time = message.text.strip()
    
    if ':' not in new_time:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    try:
        hour, minute = map(int, new_time.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            await message.answer("❌ Неверное время. Часы: 0-23, минуты: 0-59")
            return
    except:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    data = await state.get_data()
    old_day = data['old_day']
    old_time = data['old_time']
    new_day = data['new_day']
    user_ids = data['user_ids']
    is_group = data['is_group']
    
    # Проверяем конфликты времени (исключая переносимые уроки)
    schedule = await db.get_schedule()
    existing_times = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == new_day:
                # Исключаем переносимые уроки
                if not (lesson['day'] == old_day and lesson['time'] == old_time):
                    existing_times.append(lesson['time'])
    
    has_conflict, conflict_time = check_time_conflict(new_time, existing_times)
    
    if has_conflict:
        await message.answer(
            f"❌ Конфликт времени!\n\n"
            f"Урок в {new_time} пересекается с уроком в {conflict_time}.\n"
            f"Урок длится 1 час. Выбери другое время."
        )
        return
    
    # Удаляем старые уроки и добавляем новые
    for user_id in user_ids:
        await db.remove_lesson_from_schedule(int(user_id), old_day, old_time)
        await db.add_lesson_to_schedule(int(user_id), new_day, new_time)
    
    day_names_ru = {
        'monday': 'Пн',
        'tuesday': 'Вт',
        'wednesday': 'Ср',
        'thursday': 'Чт',
        'friday': 'Пт',
        'saturday': 'Сб',
        'sunday': 'Вс'
    }
    
    if is_group:
        await message.answer(f"✅ Групповой урок перенесен!\n\n{day_names_ru[old_day]} {old_time} → {day_names_ru[new_day]} {new_time}")
    else:
        await message.answer(f"✅ Урок перенесен!\n\n{day_names_ru[old_day]} {old_time} → {day_names_ru[new_day]} {new_time}")
    
    await state.clear()
    await show_admin_menu(message)

@router.callback_query(F.data == "move_back_to_days")
async def move_back_to_days(callback: CallbackQuery, state: FSMContext):
    # Возвращаемся к выбору дня
    await state.set_state(LessonManagement.moving_lesson_select_day)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="moveday_monday")],
        [InlineKeyboardButton(text="Вторник", callback_data="moveday_tuesday")],
        [InlineKeyboardButton(text="Среда", callback_data="moveday_wednesday")],
        [InlineKeyboardButton(text="Четверг", callback_data="moveday_thursday")],
        [InlineKeyboardButton(text="Пятница", callback_data="moveday_friday")],
        [InlineKeyboardButton(text="Суббота", callback_data="moveday_saturday")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="moveday_sunday")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_move")]
    ])
    
    await callback.message.edit_text(
        f"🔄 Перенос урока\n\nВыбери новый день недели:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "cancel_move")
async def cancel_move(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_admin_menu(callback.message)

# === Управление учениками ===

@router.callback_query(F.data == "admin_students")
async def show_students_list(callback: CallbackQuery):
    await show_students_page(callback, 0)

@router.callback_query(F.data.startswith("students_page_"))
async def show_students_page_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    await show_students_page(callback, page)

async def show_students_page(callback: CallbackQuery, page: int):
    students = await db.get_students()
    schedule = await db.get_schedule()
    
    if not students:
        await callback.message.edit_text("👥 Пока нет зарегистрированных учеников.")
        return
    
    # Сортируем учеников по имени
    students_list = []
    for user_id, student in students.items():
        name = student.get('name', 'Без имени')
        username = student.get('username', '')
        user_schedule = schedule.get(user_id, [])
        lessons_count = len(user_schedule)
        
        students_list.append({
            'user_id': user_id,
            'name': name,
            'username': username,
            'lessons_count': lessons_count
        })
    
    students_list.sort(key=lambda x: x['name'])
    
    # Пагинация
    per_page = 5
    total_students = len(students_list)
    total_pages = (total_students + per_page - 1) // per_page
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_students)
    
    page_students = students_list[start_idx:end_idx]
    
    message_text = f"👥 Список учеников (стр. {page + 1}/{total_pages})\n\n"
    
    keyboard_buttons = []
    
    for idx, student in enumerate(page_students, start=start_idx + 1):
        name = student['name']
        username = student['username']
        username_str = f"@{username}" if username else ""
        lessons_count = student['lessons_count']
        user_id = student['user_id']
        
        if lessons_count > 0:
            message_text += f"{idx}. ✅ {name} {username_str}\n   📚 {lessons_count} {'урок' if lessons_count == 1 else 'уроков'} в неделю\n\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{idx}. {name}",
                callback_data=f"edit_schedule_{user_id}"
            )])
        else:
            message_text += f"{idx}. {name} {username_str}\n   ⚠️ Расписание не назначено\n\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{idx}. {name}",
                callback_data=f"add_schedule_{user_id}"
            )])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"students_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"students_page_{page + 1}"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("edit_schedule_"))
async def edit_student_schedule(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    student = await db.get_student(user_id)
    schedule = await db.get_student_schedule(user_id)
    
    if not student:
        await callback.answer("Ошибка: ученик не найден")
        return
    
    name = student.get('name', 'Ученик')
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    message_text = f"📝 Расписание ученика: {name}\n\n"
    
    if schedule:
        # Группируем по дням
        schedule_by_day = {}
        for lesson in schedule:
            day = lesson['day']
            if day not in schedule_by_day:
                schedule_by_day[day] = []
            schedule_by_day[day].append(lesson['time'])
        
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day in days_order:
            if day in schedule_by_day:
                message_text += f"📌 {day_names_ru[day]}\n"
                for time in sorted(schedule_by_day[day]):
                    message_text += f"   ⏰ {time}\n"
                message_text += "\n"
    else:
        message_text += "⚠️ Расписание пусто\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить урок", callback_data=f"add_schedule_{user_id}")],
        [InlineKeyboardButton(text="◀️ К списку учеников", callback_data="admin_students")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("add_schedule_"))
async def start_add_schedule(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[2]
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(ScheduleManagement.selecting_day)
    
    student = await db.get_student(int(user_id))
    name = student.get('name', 'Ученик')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="day_monday")],
        [InlineKeyboardButton(text="Вторник", callback_data="day_tuesday")],
        [InlineKeyboardButton(text="Среда", callback_data="day_wednesday")],
        [InlineKeyboardButton(text="Четверг", callback_data="day_thursday")],
        [InlineKeyboardButton(text="Пятница", callback_data="day_friday")],
        [InlineKeyboardButton(text="Суббота", callback_data="day_saturday")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="day_sunday")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_schedule")]
    ])
    
    await callback.message.edit_text(
        f"📝 Настройка расписания для {name}\n\nВыбери день недели:",
        reply_markup=keyboard
    )
@router.callback_query(F.data.startswith("edit_schedule_"))
async def edit_student_schedule(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])

    student = await db.get_student(user_id)
    schedule = await db.get_student_schedule(user_id)

    if not student:
        await callback.answer("Ошибка: ученик не найден")
        return

    name = student.get('name', 'Ученик')

    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }

    message_text = f"📝 Расписание ученика: {name}\n\n"

    if schedule:
        # Группируем по дням
        schedule_by_day = {}
        for lesson in schedule:
            day = lesson['day']
            if day not in schedule_by_day:
                schedule_by_day[day] = []
            schedule_by_day[day].append(lesson['time'])

        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        for day in days_order:
            if day in schedule_by_day:
                message_text += f"📌 {day_names_ru[day]}\n"
                for time in sorted(schedule_by_day[day]):
                    message_text += f"   ⏰ {time}\n"
                message_text += "\n"
    else:
        message_text += "⚠️ Расписание пусто\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить урок", callback_data=f"add_schedule_{user_id}")],
        [InlineKeyboardButton(text="◀️ К списку учеников", callback_data="admin_students")]
    ])

    await callback.message.edit_text(message_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("day_"), ScheduleManagement.selecting_day)
async def process_day_selection(callback: CallbackQuery, state: FSMContext):
    day = callback.data.split("_")[1]
    
    await state.update_data(selected_day=day)
    await state.set_state(ScheduleManagement.selecting_time)
    
    # Получаем занятые времена
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
    
    day_names_ru = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }
    
    message_text = f"📅 {day_names_ru[day]}\n\nДоступное время:\n\n"
    
    time_slots = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', 
                  '16:00', '17:00', '18:00', '19:00', '20:00', '21:00']
    
    keyboard_buttons = []
    row = []
    
    for time in time_slots:
        if time in occupied_times:
            message_text += f"❌ {time} - занято ({', '.join(occupied_times[time])})\n"
            row.append(InlineKeyboardButton(text=f"❌ {time}", callback_data=f"time_{time}_occupied"))
        else:
            message_text += f"✅ {time} - \n"
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
        await callback.message.edit_text("✏️ Введи время в формате ЧЧ:ММ (например, 15:30):")
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
        
        message = f"⚠️ Внимание!\n\nВ {day_names_ru[selected_day]} {time} уже назначен урок:\n"
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
    
    await callback.message.edit_text(f"✅ Урок добавлен!\n\n{student_name} - {selected_day} {time}")
    
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
    
    await callback.message.edit_text(f"✅ Групповое занятие создано!\n\n{student_name} добавлен в {selected_day} {time}")
    
    await state.clear()

@router.message(ScheduleManagement.custom_time)
async def process_custom_time(message: Message, state: FSMContext):
    time = message.text.strip()
    
    if not time or ':' not in time:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    try:
        hour, minute = map(int, time.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            await message.answer("❌ Неверное время. Часы: 0-23, минуты: 0-59")
            return
    except:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 15:30):")
        return
    
    data = await state.get_data()
    target_user_id = int(data['target_user_id'])
    selected_day = data['selected_day']
    
    # Проверяем конфликты времени
    schedule = await db.get_schedule()
    existing_times = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == selected_day:
                existing_times.append(lesson['time'])
    
    has_conflict, conflict_time = check_time_conflict(time, existing_times)
    
    if has_conflict:
        await message.answer(
            f"❌ Конфликт времени!\n\n"
            f"Урок в {time} пересекается с уроком в {conflict_time}.\n"
            f"Урок длится 1 час. Выбери другое время."
        )
        return
    
    await db.add_lesson_to_schedule(target_user_id, selected_day, time)
    
    student = await db.get_student(target_user_id)
    student_name = student.get('name', 'Ученик')
    
    await message.answer(f"✅ Урок добавлен!\n\n{student_name} - {selected_day} {time}")
    
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
    
    message_text = "⚙️ Настройки бота\n\n"
    message_text += f"🌍 Твой часовой пояс: UTC+{settings['admin_timezone']}\n\n"
    message_text += f"⏰ Напоминания ученикам:\n   За {settings['reminder_hours_before']} {'час' if settings['reminder_hours_before'] == 1 else 'часов'} до урока\n\n"
    message_text += f"📊 Отчеты по ДЗ:\n   За {settings['homework_check_minutes_before']} минут до урока\n\n"
    message_text += f"🔔 Утреннее напоминание:\n   В {settings['admin_daily_reminder_time']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Время напоминаний", callback_data="change_reminder_time")],
        [InlineKeyboardButton(text="📊 Время отчетов", callback_data="change_report_time")],
        [InlineKeyboardButton(text="🔔 Утреннее напоминание", callback_data="change_daily_time")],
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="change_timezone")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)

@router.callback_query(F.data == "change_reminder_time")
async def change_reminder_time(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsChange.waiting_for_reminder_time)
    await callback.message.edit_text(
        "⏰ Введи за сколько часов до урока отправлять напоминание:\n\n"
        "Например: 1 (за 1 час) или 2 (за 2 часа)"
    )

@router.message(SettingsChange.waiting_for_reminder_time)
async def process_reminder_time(message: Message, state: FSMContext):
    try:
        hours = int(message.text)
        if hours < 0 or hours > 24:
            await message.answer("❌ Введи число от 0 до 24")
            return
        
        await db.update_setting('reminder_hours_before', hours)
        await message.answer(f"✅ Сохранено! Напоминания будут за {hours} {'час' if hours == 1 else 'часов'} до урока.")
        await state.clear()
        await show_admin_menu(message)
    except ValueError:
        await message.answer("❌ Введи число, например: 1")

@router.callback_query(F.data == "change_report_time")
async def change_report_time(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsChange.waiting_for_report_time)
    await callback.message.edit_text(
        "📊 Введи за сколько минут до урока отправлять отчет по ДЗ:\n\n"
        "Например: 5 (за 5 минут) или 10 (за 10 минут)"
    )

@router.message(SettingsChange.waiting_for_report_time)
async def process_report_time(message: Message, state: FSMContext):
    try:
        minutes = int(message.text)
        if minutes < 0 or minutes > 120:
            await message.answer("❌ Введи число от 0 до 120")
            return
        
        await db.update_setting('homework_check_minutes_before', minutes)
        await message.answer(f"✅ Сохранено! Отчеты будут за {minutes} минут до урока.")
        await state.clear()
        await show_admin_menu(message)
    except ValueError:
        await message.answer("❌ Введи число, например: 5")

@router.callback_query(F.data == "change_daily_time")
async def change_daily_time(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsChange.waiting_for_daily_time)
    await callback.message.edit_text(
        "🔔 Введи время для утреннего напоминания:\n\n"
        "Формат: ЧЧ:ММ\n"
        "Например: 08:00 или 09:30"
    )

@router.message(SettingsChange.waiting_for_daily_time)
async def process_daily_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    if ':' not in time_str:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ, например: 08:00")
        return
    
    try:
        hour, minute = map(int, time_str.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            await message.answer("❌ Неверное время. Часы: 0-23, минуты: 0-59")
            return
        
        await db.update_setting('admin_daily_reminder_time', time_str)
        await message.answer(f"✅ Сохранено! Утреннее напоминание в {time_str}\n\n⚠️ Перезапусти бота для применения.")
        await state.clear()
        await show_admin_menu(message)
    except ValueError:
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ, например: 08:00")

@router.callback_query(F.data == "change_timezone")
async def change_timezone(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsChange.waiting_for_timezone)
    await callback.message.edit_text(
        "🌍 Введи свой часовой пояс (смещение от UTC):\n\n"
        "Например:\n"
        "3 - для МСК (UTC+3)\n"
        "2 - для Калининграда (UTC+2)\n"
        "5 - для Екатеринбурга (UTC+5)"
    )

@router.message(SettingsChange.waiting_for_timezone)
async def process_timezone(message: Message, state: FSMContext):
    try:
        tz = int(message.text)
        if tz < -12 or tz > 14:
            await message.answer("❌ Введи число от -12 до 14")
            return
        
        await db.update_setting('admin_timezone', tz)
        await message.answer(f"✅ Сохранено! Твой часовой пояс: UTC+{tz}\n\n⚠️ Перезапусти бота для применения.")
        await state.clear()
        await show_admin_menu(message)
    except ValueError:
        await message.answer("❌ Введи число, например: 3")
