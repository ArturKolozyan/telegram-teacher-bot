"""
Модуль авторизации и управления пользователями (репетиторами)
"""
import json
import os
import asyncio
import hashlib
import secrets
from datetime import datetime
from typing import Dict, Optional

DATA_DIR = 'data'
TUTORS_FILE = 'tutors.json'

# Блокировка для безопасной работы с файлом
tutor_lock = asyncio.Lock()

def ensure_data_dir():
    """Создает папку data если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path(filename: str) -> str:
    """Возвращает полный путь к файлу"""
    return os.path.join(DATA_DIR, filename)

def hash_password(password: str) -> str:
    """Хеширует пароль"""
    return hashlib.sha256(password.encode()).hexdigest()

async def load_tutors() -> Dict:
    """Загружает данные репетиторов"""
    filepath = get_file_path(TUTORS_FILE)
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки {TUTORS_FILE}: {e}")
        return {}

async def save_tutors(tutors: Dict):
    """Сохраняет данные репетиторов"""
    filepath = get_file_path(TUTORS_FILE)
    
    async with tutor_lock:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tutors, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения {TUTORS_FILE}: {e}")

async def register_tutor(email: str, password: str, name: str, telegram_id: Optional[int] = None) -> Dict:
    """
    Регистрирует нового репетитора
    Возвращает: {'success': bool, 'message': str, 'tutor_id': str}
    """
    tutors = await load_tutors()
    
    # Проверяем существует ли email
    for tutor_id, tutor in tutors.items():
        if tutor['email'] == email:
            return {'success': False, 'message': 'Email уже зарегистрирован'}
    
    # Генерируем уникальный ID
    tutor_id = secrets.token_urlsafe(16)
    
    # Создаем репетитора
    tutors[tutor_id] = {
        'tutor_id': tutor_id,
        'email': email,
        'password_hash': hash_password(password),
        'name': name,
        'telegram_id': telegram_id,
        'created_at': datetime.now().isoformat(),
        'settings': {
            'admin_timezone': 3,  # UTC+3 (МСК по умолчанию)
            'reminder_minutes_before': 60,
            'homework_check_minutes_before': 5,
            'admin_daily_reminder_time': '08:00',
            'default_lesson_price': 1000
        }
    }
    
    await save_tutors(tutors)
    
    return {
        'success': True,
        'message': 'Регистрация успешна',
        'tutor_id': tutor_id
    }

async def authenticate_tutor(email: str, password: str) -> Optional[Dict]:
    """
    Аутентифицирует репетитора
    Возвращает данные репетитора или None
    """
    tutors = await load_tutors()
    password_hash = hash_password(password)
    
    for tutor_id, tutor in tutors.items():
        if tutor['email'] == email and tutor['password_hash'] == password_hash:
            return {
                'tutor_id': tutor_id,
                'email': tutor['email'],
                'name': tutor['name'],
                'telegram_id': tutor.get('telegram_id')
            }
    
    return None

async def get_tutor_by_id(tutor_id: str) -> Optional[Dict]:
    """Получает репетитора по ID"""
    tutors = await load_tutors()
    return tutors.get(tutor_id)

async def get_tutor_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Получает репетитора по Telegram ID"""
    tutors = await load_tutors()
    
    for tutor_id, tutor in tutors.items():
        if tutor.get('telegram_id') == telegram_id:
            return tutor
    
    return None

async def update_tutor_telegram_id(tutor_id: str, telegram_id: int):
    """Обновляет Telegram ID репетитора"""
    tutors = await load_tutors()
    
    if tutor_id in tutors:
        tutors[tutor_id]['telegram_id'] = telegram_id
        await save_tutors(tutors)

async def get_tutor_settings(tutor_id: str) -> Dict:
    """Получает настройки репетитора"""
    tutor = await get_tutor_by_id(tutor_id)
    
    if not tutor:
        return {}
    
    return tutor.get('settings', {
        'admin_timezone': 3,
        'reminder_minutes_before': 60,
        'homework_check_minutes_before': 5,
        'admin_daily_reminder_time': '08:00',
        'default_lesson_price': 1000
    })

async def update_tutor_settings(tutor_id: str, settings: Dict):
    """Обновляет настройки репетитора"""
    tutors = await load_tutors()
    
    if tutor_id in tutors:
        tutors[tutor_id]['settings'] = settings
        await save_tutors(tutors)
