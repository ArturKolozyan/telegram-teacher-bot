"""
Точка входа для ASGI сервера (production)
"""
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Импортируем приложение
from web_app import app

# Создаем папку data если её нет
import database as db
db.ensure_data_dir()

# Экспортируем app для ASGI сервера
application = app
