"""
Запуск веб-сервера и Telegram бота одновременно
Для Railway используется asyncio вместо multiprocessing
"""
import asyncio
import uvicorn
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def run_bot():
    """Запуск Telegram бота"""
    from bot_notifications import main
    await main()

async def run_web():
    """Запуск веб-сервера"""
    from web_app import app
    import database as db
    db.ensure_data_dir()
    
    # Получаем порт из переменной окружения (для Railway)
    port = int(os.getenv('PORT', 8000))
    
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """Запуск бота и веб-сервера параллельно"""
    print("🚀 Запуск системы...")
    print("📱 Telegram бот: запускается...")
    print("🌐 Веб-сервер: запускается...")
    print("\nДля остановки нажмите Ctrl+C\n")
    
    # Запускаем оба процесса параллельно
    await asyncio.gather(
        run_bot(),
        run_web()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка системы...")
        print("✅ Система остановлена")
