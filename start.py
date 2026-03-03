"""
Запуск веб-сервера и Telegram бота одновременно
"""
import asyncio
import uvicorn
from multiprocessing import Process
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_bot():
    """Запуск Telegram бота"""
    from bot_notifications import main
    asyncio.run(main())

def run_web():
    """Запуск веб-сервера"""
    from web_app import app
    import database as db
    db.ensure_data_dir()
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    print("🚀 Запуск системы...")
    print("📱 Telegram бот: запускается...")
    print("🌐 Веб-сервер: http://localhost:8000")
    print("\nДля остановки нажмите Ctrl+C\n")
    
    bot_process = Process(target=run_bot, name="TelegramBot")
    web_process = Process(target=run_web, name="WebServer")
    
    try:
        bot_process.start()
        web_process.start()
        
        bot_process.join()
        web_process.join()
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка системы...")
        bot_process.terminate()
        web_process.terminate()
        bot_process.join()
        web_process.join()
        print("✅ Система остановлена")
