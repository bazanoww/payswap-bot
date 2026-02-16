from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import requests
import uvicorn
import re
from urllib.parse import urlparse, parse_qs
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
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
    
    patterns = [
        r'сумма[:\s]*(\d+[.,]?\d*)',
        r'(\d+[.,]?\d*)\s*(?:руб|р|rub|₽)',
        r'(\d+[.,]?\d*)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, qr_text.lower())
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except:
                continue
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
        data = requests.get('https://api.rapira.net/open/market/rates').json()['data']
        pairs = {'USDT/RUB': 'RUB', 'BTC/USDT': 'USDT', 'TON/USDT': 'USDT'}
        result = []
        for item in data:
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

# --- Эндпоинты ---
@app.get("/")
async def root():
    return {"message": "PaySwap API работает"}

@app.get("/api/prices")
async def api_prices():
    return JSONResponse({"prices": get_prices()})

@app.post("/api/parse-qr")
async def api_parse_qr(request: Request):
    data = await request.json()
    qr_text = data.get('qr', '')
    
    rub_amount = extract_amount_from_qr(qr_text)
    
    if rub_amount:
        usdt, rate = calculate_usdt_amount(rub_amount)
        return JSONResponse({
            "success": True,
            "qr": qr_text[:100] + "..." if len(qr_text) > 100 else qr_text,
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
    """Отдает HTML WebApp"""
    try:
        with open("webapp.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Файл webapp.html не найден</h1>", status_code=404)

@app.get("/test")
async def test():
    return {"status": "ok"}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))  # Берем порт из Render или 8000 по умолчанию
    print(f"🚀 Запуск сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)