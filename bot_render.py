import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import json
import os
from datetime import datetime

# Токен вашего бота
TOKEN = '8348646039:AAGWsSyJqLXCh1j5xyrORGI8xBgRHry6SBg'
ADMIN_ID = 6665744691

# URL вашего API на Render
API_URL = "https://payswap-bot.onrender.com"

logging.basicConfig(level=logging.INFO)

# --- Функции для API (если нужны) ---
def get_usdt_rub_price():
    try:
        response = requests.get(f"{API_URL}/api/prices")
        return response.json()
    except:
        return None

# --- Inline клавиатуры ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌐 ОТКРЫТЬ ПРИЛОЖЕНИЕ", 
                              web_app=WebAppInfo(url=f"{API_URL}/app"))],
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
        "👋 <b>PaySwap Wallet</b>\n\n"
        "💰 Оплата покупок в рублях через USDT\n\n"
        "👇 Выберите действие:",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш ID: <code>{update.message.from_user.id}</code>", parse_mode='HTML')

# --- Обработчик inline кнопок ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'menu':
        await query.edit_message_text(
            "👋 <b>Главное меню</b>",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'prices':
        try:
            response = requests.get(f"{API_URL}/api/prices")
            data = response.json()
            prices_text = "📊 <b>КУРСЫ</b>\n━━━━━━━━━━\n\n"
            for item in data['prices']:
                emoji = "📈" if item['change'] > 0 else "📉" if item['change'] < 0 else "➖"
                prices_text += f"{item['pair']}: {item['price']} {emoji} {item['change']:+.2f}%\n"
        except:
            prices_text = "Ошибка получения курсов"
        
        await query.edit_message_text(
            prices_text,
            reply_markup=back_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'orderbook':
        try:
            response = requests.get(f"{API_URL}/api/orderbook")
            data = response.json()
            book = data['orderbook']
            text = f"📈 <b>СТАКАН USDT/RUB</b>\n━━━━━━━━━━━━\n\nASK: {book['ask']} RUB\nBID: {book['bid']} RUB\nСпред: {book['spread']} RUB ({book['spread_percent']}%)"
        except:
            text = "Ошибка получения стакана"
        
        await query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'about':
        await query.edit_message_text(
            "ℹ️ <b>О БОТЕ</b>\n━━━━━━━━\n\n"
            "• Курсы BTC/USDT, USDT/RUB, TON/USDT\n"
            "• Стакан USDT/RUB\n"
            "• Оплата по QR с расчетом USDT (+5%)\n\n"
            "Данные с биржи <a href='https://t.me/RapiraNetBot/app?startapp=ref_0T17'>Rapira</a>",
            reply_markup=back_keyboard(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )

# --- Обработчик данных из WebApp ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print("🔥 ПОЛУЧЕНЫ ДАННЫЕ ИЗ WEBAPP!")
        data = json.loads(update.effective_message.web_app_data.data)
        print(f"🔥 Данные: {data}")
        
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
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                parse_mode='HTML'
            )
            print("✅ Уведомление отправлено админу")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# --- Главная функция ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    print('🚀 Бот запущен на Render...')
    print(f'👑 ADMIN ID: {ADMIN_ID}')
    print(f'🌐 API URL: {API_URL}')
    
    app.run_polling()

if __name__ == '__main__':
    main()