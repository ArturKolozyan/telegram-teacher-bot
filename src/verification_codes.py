"""
Управление кодами подтверждения
"""
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

DATA_DIR = 'data'
CODES_FILE = 'verification_codes.json'

def get_file_path() -> str:
    return os.path.join(DATA_DIR, CODES_FILE)

def load_codes() -> Dict:
    """Загрузить коды"""
    filepath = get_file_path()
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки кодов: {e}")
        return {}

def save_codes(codes: Dict):
    """Сохранить коды"""
    filepath = get_file_path()
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(codes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения кодов: {e}")

def generate_code() -> str:
    """Генерировать 4-значный код"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(4)])

def create_verification_code(email: str, name: str = None) -> str:
    """Создать код подтверждения для email"""
    codes = load_codes()
    
    # Удаляем старые коды
    clean_expired_codes()
    
    # Генерируем новый код
    code = generate_code()
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    codes[email] = {
        'code': code,
        'name': name,
        'expires_at': expires_at,
        'created_at': datetime.now().isoformat()
    }
    
    save_codes(codes)
    return code

def verify_code(email: str, code: str) -> bool:
    """Проверить код подтверждения"""
    codes = load_codes()
    
    if email not in codes:
        return False
    
    stored = codes[email]
    
    # Проверяем срок действия
    expires_at = datetime.fromisoformat(stored['expires_at'])
    if datetime.now() > expires_at:
        # Код истек
        del codes[email]
        save_codes(codes)
        return False
    
    # Проверяем код
    if stored['code'] == code:
        # Код верный - удаляем его
        del codes[email]
        save_codes(codes)
        return True
    
    return False

def clean_expired_codes():
    """Удалить истекшие коды"""
    codes = load_codes()
    now = datetime.now()
    
    expired = []
    for email, data in codes.items():
        expires_at = datetime.fromisoformat(data['expires_at'])
        if now > expires_at:
            expired.append(email)
    
    for email in expired:
        del codes[email]
    
    if expired:
        save_codes(codes)
