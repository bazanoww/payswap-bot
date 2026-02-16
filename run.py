import os
import threading
import uvicorn
import subprocess
import sys

def run_bot():
    """Запускает бота в отдельном процессе"""
    subprocess.run([sys.executable, "bot.py"])

def run_api():
    """Запускает API сервер"""
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    print("🚀 Запуск API сервера и бота...")
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем API в основном потоке
    run_api()