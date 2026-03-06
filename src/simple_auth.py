"""
Простая система авторизации для одного репетитора
"""
import json
import os
import hashlib
from typing import Optional, Dict

DATA_DIR = 'data'
AUTH_FILE = 'tutor_auth.json'

def ensure_data_dir():
    """Создает папку data если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path() -> str:
    """Возвращает путь к файлу авторизации"""
    return os.path.join(DATA_DIR, AUTH_FILE)

def hash_password(password: str) -> str:
    """Хеширует пароль"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_auth() -> Optional[Dict]:
    """Загружает данные авторизации"""
    filepath = get_file_path()
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки авторизации: {e}")
        return None

def save_auth(data: Dict):
    """Сохраняет данные авторизации"""
    ensure_data_dir()
    filepath = get_file_path()
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения авторизации: {e}")

def is_registered() -> bool:
    """Проверяет зарегистрирован ли репетитор"""
    auth_data = load_auth()
    return auth_data is not None

def register(email: str, password: str, name: str) -> Dict:
    """
    Регистрирует репетитора
    Возвращает: {'success': bool, 'message': str, 'tutor_id': str}
    """
    if is_registered():
        return {'success': False, 'message': 'Репетитор уже зарегистрирован'}
    
    # Генерируем уникальный ID репетитора (короткий и читаемый)
    import secrets
    tutor_id = secrets.token_urlsafe(8)  # Например: "a7B9cD2e"
    
    auth_data = {
        'tutor_id': tutor_id,
        'email': email,
        'password_hash': hash_password(password),
        'name': name
    }
    
    save_auth(auth_data)
    
    return {
        'success': True,
        'message': 'Регистрация успешна',
        'tutor_id': tutor_id
    }

def authenticate(email: str, password: str) -> bool:
    """Проверяет email и пароль"""
    auth_data = load_auth()
    
    if not auth_data:
        return False
    
    password_hash = hash_password(password)
    
    return (auth_data['email'] == email and 
            auth_data['password_hash'] == password_hash)

def get_tutor_info() -> Optional[Dict]:
    """Получает информацию о репетиторе"""
    auth_data = load_auth()
    
    if not auth_data:
        return None
    
    return {
        'tutor_id': auth_data.get('tutor_id'),
        'email': auth_data['email'],
        'name': auth_data['name']
    }

def get_tutor_id() -> Optional[str]:
    """Получает ID репетитора"""
    auth_data = load_auth()
    
    if not auth_data:
        return None
    
    return auth_data.get('tutor_id')
