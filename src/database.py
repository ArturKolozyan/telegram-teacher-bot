import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

# Блокировки для безопасной работы с файлами
locks = {
    'students': asyncio.Lock(),
    'schedule': asyncio.Lock(),
    'settings': asyncio.Lock(),
    'homework': asyncio.Lock()
}

DATA_DIR = 'data'

def ensure_data_dir():
    """Создает папку data если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path(filename: str) -> str:
    """Возвращает полный путь к файлу"""
    return os.path.join(DATA_DIR, filename)

async def load_json(filename: str, default: dict = None) -> dict:
    """Загружает данные из JSON файла"""
    filepath = get_file_path(filename)
    
    if not os.path.exists(filepath):
        return default if default is not None else {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки {filename}: {e}")
        return default if default is not None else {}

async def save_json(filename: str, data: dict, lock_name: str):
    """Сохраняет данные в JSON файл с блокировкой"""
    filepath = get_file_path(filename)
    
    async with locks[lock_name]:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения {filename}: {e}")

# === Работа с учениками ===

async def get_students() -> Dict:
    """Получить всех учеников"""
    return await load_json('students.json', {})

async def save_students(students: Dict):
    """Сохранить учеников"""
    await save_json('students.json', students, 'students')

async def add_student(user_id: int, name: str, username: str, timezone_offset: int):
    """Добавить нового ученика"""
    students = await get_students()
    students[str(user_id)] = {
        'user_id': user_id,
        'name': name,
        'username': username,
        'timezone_offset': timezone_offset,
        'registered_at': datetime.now().isoformat()
    }
    await save_students(students)

async def get_student(user_id: int) -> Optional[Dict]:
    """Получить ученика по ID"""
    students = await get_students()
    return students.get(str(user_id))

async def update_student_timezone(user_id: int, timezone_offset: int):
    """Обновить часовой пояс ученика"""
    students = await get_students()
    if str(user_id) in students:
        students[str(user_id)]['timezone_offset'] = timezone_offset
        await save_students(students)

# === Работа с расписанием ===

async def get_schedule() -> Dict:
    """Получить все расписание"""
    return await load_json('schedule.json', {})

async def save_schedule(schedule: Dict):
    """Сохранить расписание"""
    await save_json('schedule.json', schedule, 'schedule')

async def get_student_schedule(user_id: int) -> List[Dict]:
    """Получить расписание ученика"""
    schedule = await get_schedule()
    return schedule.get(str(user_id), [])

async def set_student_schedule(user_id: int, lessons: List[Dict]):
    """Установить расписание ученика"""
    schedule = await get_schedule()
    schedule[str(user_id)] = lessons
    await save_schedule(schedule)

async def add_lesson_to_schedule(user_id: int, day: str, time: str):
    """Добавить урок в расписание"""
    schedule = await get_schedule()
    user_schedule = schedule.get(str(user_id), [])
    user_schedule.append({'day': day, 'time': time})
    schedule[str(user_id)] = user_schedule
    await save_schedule(schedule)

async def remove_lesson_from_schedule(user_id: int, day: str, time: str):
    """Удалить урок из расписания навсегда"""
    schedule = await get_schedule()
    user_schedule = schedule.get(str(user_id), [])
    user_schedule = [l for l in user_schedule if not (l['day'] == day and l['time'] == time)]
    schedule[str(user_id)] = user_schedule
    await save_schedule(schedule)

# === Работа с настройками ===

async def get_settings() -> Dict:
    """Получить настройки"""
    default_settings = {
        'admin_timezone': 3,  # UTC+3 МСК
        'reminder_hours_before': 1,
        'homework_check_minutes_before': 5,
        'admin_daily_reminder_time': '08:00'
    }
    return await load_json('settings.json', default_settings)

async def save_settings(settings: Dict):
    """Сохранить настройки"""
    await save_json('settings.json', settings, 'settings')

async def update_setting(key: str, value):
    """Обновить одну настройку"""
    settings = await get_settings()
    settings[key] = value
    await save_settings(settings)

# === Работа с ответами по ДЗ ===

async def get_homework_responses() -> Dict:
    """Получить все ответы по ДЗ"""
    return await load_json('homework_responses.json', {})

async def save_homework_responses(responses: Dict):
    """Сохранить ответы по ДЗ"""
    await save_json('homework_responses.json', responses, 'homework')

async def save_homework_response(date: str, time: str, user_id: int, status: str, reason: str = None):
    """Сохранить ответ ученика по ДЗ"""
    responses = await get_homework_responses()
    key = f"{date}_{time}_{user_id}"
    responses[key] = {
        'date': date,
        'time': time,
        'user_id': user_id,
        'status': status,
        'reason': reason,
        'responded_at': datetime.now().isoformat()
    }
    await save_homework_responses(responses)

async def get_homework_response(date: str, time: str, user_id: int) -> Optional[Dict]:
    """Получить ответ ученика по ДЗ"""
    responses = await get_homework_responses()
    key = f"{date}_{time}_{user_id}"
    return responses.get(key)
