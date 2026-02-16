import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import re
from urllib.parse import urlparse, parse_qs
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import json
from datetime import datetime
import threading

# Токен вашего бота
TOKEN = '8348646039:AAGWsSyJqLXCh1j5xyrORGI8xBgRHry6SBg'
ADMIN_ID = 6665744691

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ========== FASTAPI ЧАСТЬ (WebApp и API) ==========
app = FastAPI()

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Функции парсинга ---
def get_usdt_rub_price():
    try:
        url = 'https://api.rapira.net/open/market/rates'
        response = requests.get(url)
        data = response.json()
        
        for item in data['data']:
            if item['symbol'] == 'USDT/RUB':
                return float(item['close'])
        return None
    except:
        return None

def extract_amount_from_qr(qr_text: str):
    if 'qr.nspk.ru' in qr_text and 'sum=' in qr_text:
        try:
            parsed = urlparse(qr_text)
            params = parse_qs(parsed.query)
            if 'sum' in params:
                return int(params['sum'][0]) / 100
        except:
            pass
    return None

def calculate_usdt_amount(rub_amount: float):
    usdt_rate = get_usdt_rub_price()
    if not usdt_rate:
        return None, None
    
    rate_with_markup = usdt_rate * 1.05
    usdt_amount = rub_amount / rate_with_markup
    return round(usdt_amount, 2), round(usdt_rate, 2)

def get_prices():
    try:
        url = 'https://api.rapira.net/open/market/rates'
        response = requests.get(url)
        data = response.json()
        
        pairs = {'USDT/RUB': 'RUB', 'BTC/USDT': 'USDT', 'TON/USDT': 'USDT'}
        result = []
        
        for item in data['data']:
            if item['symbol'] in pairs:
                change = float(item.get('chg', 0)) * 100
                result.append({
                    'pair': item['symbol'],
                    'price': item['close'],
                    'currency': pairs[item['symbol']],
                    'change': round(change, 2)
                })
        return result
    except:
        return []

def get_order_book():
    try:
        url = 'https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB'
        response = requests.get(url)
        data = response.json()
        
        ask = data['ask']['items'][0]['price']
        bid = data['bid']['items'][0]['price']
        spread = ask - bid
        spread_percent = (spread / bid) * 100
        
        return {
            'ask': ask,
            'bid': bid,
            'spread': round(spread, 2),
            'spread_percent': round(spread_percent, 2)
        }
    except:
        return None

# --- Эндпоинты API ---
@app.get("/")
async def root():
    return {"message": "PaySwap API работает"}

@app.get("/test")
async def test():
    return {"status": "ok"}

@app.get("/api/prices")
async def api_prices():
    return JSONResponse({"prices": get_prices()})

@app.get("/api/orderbook")
async def api_orderbook():
    book = get_order_book()
    return JSONResponse({"orderbook": book})

@app.post("/api/parse-qr")
async def api_parse_qr(request: Request):
    data = await request.json()
    qr_text = data.get('qr', '')
    
    rub_amount = extract_amount_from_qr(qr_text)
    
    if rub_amount:
        usdt, rate = calculate_usdt_amount(rub_amount)
        return JSONResponse({
            "success": True,
            "qr": qr_text[:100] + "...",
            "rub": rub_amount,
            "usdt": usdt,
            "rate": rate,
            "rate_with_markup": round(rate * 1.05, 2) if rate else None
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Сумма не найдена в QR"
        })

@app.get("/app", response_class=HTMLResponse)
async def webapp():
    try:
        with open("webapp.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Файл webapp.html не найден</h1>", status_code=404)

# ========== TELEGRAM БОТ ЧАСТЬ ==========
telegram_app = Application.builder().token(TOKEN).build()

# --- Функции для клавиатур ---
def get_main_keyboard():
    webapp_url = "https://payswap-bot.onrender.com/app"
    keyboard = [
        [InlineKeyboardButton("🌐 ОТКРЫТЬ ПРИЛОЖЕНИЕ", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("📊 КУРСЫ", callback_data='prices')],
        [InlineKeyboardButton("📈 СТАКАН", callback_data='orderbook')],
        [InlineKeyboardButton("ℹ️ О БОТЕ", callback_data='about')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>PaySwap Wallet</b>\n\n💰 Оплата покупок в рублях через USDT",
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш ID: <code>{update.message.from_user.id}</code>", parse_mode='HTML')

# --- Обработчик inline кнопок ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'menu':
        await query.edit_message_text("👋 <b>Главное меню</b>", reply_markup=get_main_keyboard(), parse_mode='HTML')
    elif query.data == 'prices':
        prices = get_prices()
        text = "📊 <b>КУРСЫ</b>\n━━━━━━━━━━\n\n"
        for p in prices:
            emoji = "📈" if p['change'] > 0 else "📉" if p['change'] < 0 else "➖"
            text += f"{p['pair']}: {p['price']} {emoji} {p['change']:+.2f}%\n"
        await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode='HTML')
    elif query.data == 'orderbook':
        book = get_order_book()
        if book:
            text = f"📈 <b>СТАКАН USDT/RUB</b>\n━━━━━━━━━━━━\n\nASK: {book['ask']} RUB\nBID: {book['bid']} RUB\nСпред: {book['spread']} RUB ({book['spread_percent']}%)"
        else:
            text = "Ошибка"
        await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode='HTML')
    elif query.data == 'about':
        await query.edit_message_text(
            "ℹ️ <b>О БОТЕ</b>\n━━━━━━━━\n\nДанные с биржи <a href='https://t.me/RapiraNetBot/app?startapp=ref_0T17'>Rapira</a>",
            reply_markup=back_keyboard(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )

# --- Обработчик данных из WebApp ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        print(f"🔥 Данные из WebApp: {data}")
        
        if data.get('type') == 'qr_scan':
            user = data.get('user', {})
            qr = data.get('qr', '')
            rub = data.get('rub', 0)
            usdt = data.get('usdt', 0)
            
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            username = user.get('username', 'нет')
            user_id = user.get('id', 'неизвестно')
            
            message = (
                f"🔍 <b>QR ИЗ WEBAPP</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 {name or 'Неизвестно'} (@{username})\n"
                f"🆔 <code>{user_id}</code>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"💰 {rub} RUB → {usdt} USDT\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"<b>Ссылка:</b>\n<pre>{qr}</pre>"
            )
            
            await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode='HTML')
            print("✅ Уведомление отправлено админу")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# --- Регистрация обработчиков бота ---
telegram_app.add_handler(CommandHandler('start', start))
telegram_app.add_handler(CommandHandler('myid', myid))
telegram_app.add_handler(CallbackQueryHandler(button_callback))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

# ========== ФУНКЦИЯ ЗАПУСКА БОТА В ОТДЕЛЬНОМ ПОТОКЕ ==========
def run_bot():
    print("🤖 Запуск Telegram бота...")
    telegram_app.run_polling()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем FastAPI сервер
    print("🚀 Запуск FastAPI сервера...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)