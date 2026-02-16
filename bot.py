from telegram import WebAppInfo
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import cv2
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

TOKEN = '8348646039:AAGWsSyJqLXCh1j5xyrORGI8xBgRHry6SBg'
ADMIN_ID = 6665744691

logging.basicConfig(level=logging.INFO)

# --- Получение курса USDT/RUB ---
async def get_usdt_rub_price():
    try:
        url = 'https://api.rapira.net/open/market/rates'
        response = requests.get(url)
        data = response.json()
        
        for item in data['data']:
            if item['symbol'] == 'USDT/RUB':
                return float(item['close'])
        return None
    except Exception as e:
        print(f"Ошибка получения курса: {e}")
        return None

# --- Расчет суммы списания в USDT (курс +5%) ---
async def calculate_usdt_amount(rub_amount: float):
    usdt_rate = await get_usdt_rub_price()
    if not usdt_rate:
        return None, None
    
    # Курс с наценкой 5%
    rate_with_markup = usdt_rate * 1.05
    usdt_amount = rub_amount / rate_with_markup
    
    return round(usdt_amount, 2), round(usdt_rate, 2)

# --- Поиск суммы в тексте QR (обновленная версия) ---
def extract_amount_from_qr(qr_text: str):
    # Проверяем, является ли QR ссылкой СБП (qr.nspk.ru)
    if 'qr.nspk.ru' in qr_text and 'sum=' in qr_text:
        try:
            # Разбираем URL параметры
            parsed = urlparse(qr_text)
            params = parse_qs(parsed.query)
            
            if 'sum' in params:
                # Сумма в копейках, конвертируем в рубли
                sum_kopecks = int(params['sum'][0])
                sum_rubles = sum_kopecks / 100
                return sum_rubles
        except Exception as e:
            print(f"Ошибка парсинга ссылки СБП: {e}")
    
    # Если это не ссылка СБП, ищем другие паттерны
    patterns = [
        r'сумма[:\s]*(\d+[.,]?\d*)',
        r'(\d+[.,]?\d*)\s*(?:руб|р|rub|₽)',
        r'(\d+[.,]?\d*)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, qr_text.lower())
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                return float(amount_str)
            except:
                continue
    
    return None

# --- Парсинг курсов ---
async def get_prices():
    try:
        data = requests.get('https://api.rapira.net/open/market/rates').json()['data']
        pairs = {'USDT/RUB': 'RUB', 'BTC/USDT': 'USDT', 'TON/USDT': 'USDT'}
        result = ""
        for item in data:
            if item['symbol'] in pairs:
                change = float(item.get('chg', 0)) * 100
                emoji = "📈" if change > 0 else "📉" if change < 0 else "➖"
                result += f"{item['symbol']}: {item['close']} {pairs[item['symbol']]} {emoji} {change:+.2f}%\n"
        return result or "Ошибка"
    except:
        return "Ошибка получения курсов"

# --- Парсинг стакана ---
async def get_order_book():
    try:
        data = requests.get('https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB').json()
        ask = data['ask']['items'][0]['price']
        bid = data['bid']['items'][0]['price']
        spread = ask - bid
        spread_percent = (spread / bid) * 100
        return f"ASK: {ask} RUB\nBID: {bid} RUB\nСпред: {spread:.2f} RUB ({spread_percent:.2f}%)"
    except:
        return "Ошибка получения стакана"

# --- Уведомление админу о QR с расчетом суммы (обновленная версия) ---
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_info: dict, qr_data: str):
    try:
        # Определяем тип QR
        is_sbp = 'qr.nspk.ru' in qr_data
        
        # Ищем сумму в QR
        amount_rub = extract_amount_from_qr(qr_data)
        
        # Формируем сообщение
        message = f"🔍 <b>НОВЫЙ QR-КОД</b>\n"
        message += f"━━━━━━━━━━━━━━━━\n"
        message += f"👤 {user_info['name']} (@{user_info['username']})\n"
        message += f"🆔 <code>{user_info['id']}</code>\n"
        message += f"📅 {user_info['time']}\n"
        
        if is_sbp:
            message += f"💳 <b>Тип:</b> СБП (платеж)\n"
        
        message += f"━━━━━━━━━━━━━━━━\n"
        
        if amount_rub:
            # Получаем курс и рассчитываем USDT
            usdt_amount, usdt_rate = await calculate_usdt_amount(amount_rub)
            
            if usdt_amount:
                message += f"💰 <b>СУММА ОПЛАТЫ:</b>\n"
                message += f"• {amount_rub:.2f} RUB\n"
                message += f"• {usdt_amount:.2f} USDT\n\n"
                message += f"📊 <b>КУРС:</b>\n"
                message += f"• Биржа: {usdt_rate:.2f} RUB/USDT\n"
                message += f"• Списание: {usdt_rate*1.05:.2f} RUB/USDT (+5%)\n"
            else:
                message += f"❌ Не удалось получить курс\n"
        else:
            message += f"⚠️ <b>Сумма не найдена в QR</b>\n"
        
        message += f"━━━━━━━━━━━━━━━━\n"
        message += f"<b>СОДЕРЖИМОЕ QR:</b>\n<pre>{qr_data}</pre>"
        
        # Отправляем админу
        await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode='HTML')
        
        # Если есть ссылка
        if qr_data.startswith(('http://', 'https://')):
            keyboard = [[InlineKeyboardButton("🔗 Перейти по ссылке", url=qr_data)]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="🔗 <b>Ссылка из QR:</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"Ошибка уведомления: {e}")

# --- Inline клавиатуры ---
def main_menu_keyboard():
    # URL нашего локального сервера
    webapp_url = "https://payswap-bot.onrender.com/app"
    
    keyboard = [
        [InlineKeyboardButton("🌐 ОТКРЫТЬ ПРИЛОЖЕНИЕ", 
                              web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("📊 КУРСЫ", callback_data='prices')],
        [InlineKeyboardButton("📈 СТАКАН", callback_data='orderbook')],
        [InlineKeyboardButton("🔍 QR-СКАНЕР", callback_data='qr')],
        [InlineKeyboardButton("ℹ️ О БОТЕ", callback_data='about')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data='menu')]]
    return InlineKeyboardMarkup(keyboard)

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Добро пожаловать в PaySwap Wallet!</b>\n\n"
        "💰 <b>Оплачивайте любые покупки в рублях с помощью USDT</b>\n\n"
        "🔍 <b>Как это работает:</b>\n"
        "1️⃣ Отсканируйте QR-код оплаты (СБП)\n"
        "2️⃣ Бот автоматически определит сумму в рублях\n"
        "3️⃣ Рассчитает сумму списания в USDT по курсу +5%\n"
        "4️⃣ Вы получите точную сумму к оплате\n\n"
        
        "📊 <b>Доступные функции:</b>\n"
        "• Курсы BTC/USDT, USDT/RUB, TON/USDT в реальном времени\n"
        "• Глубокий стакан USDT/RUB с лучшими ценами\n"
        "• Мгновенный расчет USDT по QR-кодам СБП\n\n"
        
        "💎 <b>Преимущества:</b>\n"
        "• Прозрачный курс от биржи Rapira\n"
        "• Комиссия всего 5% (уже включена в расчет)\n"
        "• Мгновенное уведомление администратора\n"
        "• Поддержка всех платежных QR СБП\n\n"
        
        "👇 <b>Выберите действие в меню ниже:</b>",
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
        prices = await get_prices()
        await query.edit_message_text(
            f"📊 <b>КУРСЫ</b>\n━━━━━━━━━━━━\n\n{prices}",
            reply_markup=back_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'orderbook':
        book = await get_order_book()
        await query.edit_message_text(
            f"📈 <b>СТАКАН USDT/RUB</b>\n━━━━━━━━━━━━\n\n{book}",
            reply_markup=back_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'qr':
        await query.edit_message_text(
            "📸 <b>QR-СКАНЕР</b>\n━━━━━━━━━━\n\n"
            "Отправьте фото с QR-кодом оплаты\n\n"
            "✅ Бот определит сумму и рассчитает списание в USDT (+5%)",
            reply_markup=back_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == 'about':
        await query.edit_message_text(
            "ℹ️ <b>О БОТЕ</b>\n━━━━━━━━\n\n"
            "• Курсы BTC/USDT, USDT/RUB, TON/USDT\n"
            "• Стакан USDT/RUB\n"
            "• Оплата ваших покупок по QR-коду с помощью USDT\n\n"
            "Парсинг курса с биржи <a href='https://t.me/RapiraNetBot/app?startapp=ref_0T17'>Rapira</a>",
            reply_markup=back_keyboard(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )

# --- Обработчик фото ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Обработка...")
    
    try:
        # Скачиваем фото
        photo = await update.message.photo[-1].get_file()
        path = 'temp_qr.jpg'
        await photo.download_to_drive(path)
        
        # Читаем QR
        img = cv2.imread(path)
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        os.remove(path)
        
        if data:
            # Инфо о пользователе
            user = update.message.from_user
            user_info = {
                'id': user.id,
                'name': user.full_name,
                'username': user.username or 'нет',
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Отправляем админу
            await notify_admin(context, user_info, data)
            
            # Ищем сумму для ответа пользователю
            amount = extract_amount_from_qr(data)
            if amount:
                usdt, rate = await calculate_usdt_amount(amount)
                if usdt:
                    await msg.edit_text(
                        f"✅ <b>QR оплачен</b>\n\n"
                        f"Сумма: {amount:.2f} RUB\n"
                        f"К списанию: {usdt:.2f} USDT\n"
                        f"Курс: {rate:.2f} (+5% = {rate*1.05:.2f})",
                        parse_mode='HTML'
                    )
                else:
                    await msg.edit_text("✅ QR отправлен администратору")
            else:
                await msg.edit_text("✅ QR отправлен администратору")
        else:
            await msg.edit_text("❌ QR не найден")
            
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает данные из WebApp и отправляет админу"""
    try:
        print("🔥 ПОЛУЧЕНЫ ДАННЫЕ ИЗ WEBAPP!")
        print(f"🔥 Сырые данные: {update.effective_message.web_app_data.data}")
        
        data = json.loads(update.effective_message.web_app_data.data)
        print(f"🔥 Распарсено: {data}")
        
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
        print(f"❌ Ошибка в handle_webapp_data: {e}")
        import traceback
        traceback.print_exc()
        
# --- Запуск ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))  # ЭТОТ

    print(f'🚀 Бот запущен | ADMIN: {ADMIN_ID}')
    app.run_polling()

if __name__ == '__main__':
    main()