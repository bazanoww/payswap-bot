import os
import threading
import uvicorn
import bot  # ИМПОРТИРУЕМ бота, а не запускаем как процесс

def run_bot():
    """Запускает бота в отдельном потоке"""
    print("🤖 Запуск бота...")
    bot.main()  # вызываем функцию main() из bot.py

def run_api():
    """Запускает API сервер"""
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Запуск API сервера на порту {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    print("🚀 Запуск API сервера и бота...")
    
    # Запускаем бота в отдельном потоке (внутри того же процесса)
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем API в основном потоке
    run_api()