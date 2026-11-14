import os
import time
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timezone
from telegram import Bot
from telegram.ext import Application

# ================== CONFIGURACIÓN ==================
TELEGRAM_TOKEN = "9100077379:AAHaMDdkLjdXYYH3r0Dvls2xyxWndlkgWmQ"
CHAT_ID = "5793293668"  # Tu ID de Telegram

# Puedes usar Twelve Data (gratis con registro) o cambiar la fuente
TWELVE_DATA_API_KEY = "35fc5d52bef34242a22585336769cb54"  # Opcional pero recomendado

SYMBOL = "XAU/USD"
INTERVAL = "5min"
CHECK_INTERVAL = 60  # Revisa cada 60 segundos

# ===================================================

bot = Bot(token=TELEGRAM_TOKEN)

def get_chat_id():
    """Función auxiliar para obtener tu Chat ID (ejecutar una vez)"""
    print("Escribe algo a tu bot y luego revisa aquí...")
    # Alternativa: usa @userinfobot en Telegram para obtener tu ID

def is_trading_time():
    now = datetime.now(timezone.utc)
    return 12 <= now.hour < 16 or (now.hour == 16 and now.minute <= 30)

def get_gold_data():
    """
    Obtiene datos de XAUUSD M5.
    Versión simple con yfinance (gratis). 
    Para mejor calidad usa Twelve Data o la API de tu broker.
    """
    try:
        import yfinance as yf
        df = yf.download("GC=F", period="5d", interval="5m", progress=False)
        df = df.tail(300)  # Últimas 300 velas
        df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in df.columns]
        return df
    except Exception as e:
        print(f"Error obteniendo datos: {e}")
        return None

def calculate_indicators(df):
    if df is None or len(df) < 200:
        return None

    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['adx'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14']

    return df

def check_buy_conditions(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 1. Tendencia
    trend = last['close'] > last['ema_50'] and last['close'] > last['ema_200']
    
    # 2. RSI
    rsi_ok = 50 <= last['rsi'] <= 65
    
    # 3. Cerca de soporte (simplificado: cerca del mínimo de las últimas 20 velas)
    recent_low = df['low'].tail(20).min()
    near_support = abs(last['close'] - recent_low) / last['close'] < 0.0015  # ~0.15%
    
    # 4. ADX
    adx_ok = last['adx'] > 20
    
    # 5. Noticias (por ahora lo dejamos como True. Luego se puede mejorar)
    news_ok = True  

    return all([trend, rsi_ok, near_support, adx_ok, news_ok]), {
        "trend": trend,
        "rsi": round(last['rsi'], 2),
        "adx": round(last['adx'], 2),
        "price": round(last['close'], 2)
    }

def check_sell_conditions(df):
    last = df.iloc[-1]

    trend = last['close'] < last['ema_50'] and last['close'] < last['ema_200']
    rsi_ok = 35 <= last['rsi'] <= 50
    
    recent_high = df['high'].tail(20).max()
    near_resistance = abs(last['close'] - recent_high) / last['close'] < 0.0015
    
    adx_ok = last['adx'] > 20
    news_ok = True

    return all([trend, rsi_ok, near_resistance, adx_ok, news_ok]), {
        "trend": trend,
        "rsi": round(last['rsi'], 2),
        "adx": round(last['adx'], 2),
        "price": round(last['close'], 2)
    }

def send_alert(message):
    try:
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        print("Alerta enviada")
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def main_loop():
    print("Bot iniciado. Esperando condiciones...")
    
    last_alert_time = 0

    while True:
        try:
            if not is_trading_time():
                print(f"[{datetime.now(timezone.utc)}] Fuera de horario")
                time.sleep(60)
                continue

            df = get_gold_data()
            df = calculate_indicators(df)

            if df is None:
                time.sleep(30)
                continue

            # Evitar alertas muy seguidas (mínimo 10 minutos entre alertas)
            if time.time() - last_alert_time < 600:
                time.sleep(30)
                continue

            # Revisar COMPRA
            buy_signal, buy_info = check_buy_conditions(df)
            if buy_signal:
                msg = f"""
🟢 <b>ALERTA DE COMPRA - XAUUSD</b>

Precio: <b>{buy_info['price']}</b>
RSI: {buy_info['rsi']}
ADX: {buy_info['adx']}

📌 <b>Configuración recomendada:</b>
• Lote: <b>0.10 Cent</b>
• Stop Loss: 500 pips (-50.00)
• Take Profit: 160 pips (+16.00)

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
                send_alert(msg)
                last_alert_time = time.time()

            # Revisar VENTA
            sell_signal, sell_info = check_sell_conditions(df)
            if sell_signal:
                msg = f"""
🔴 <b>ALERTA DE VENTA - XAUUSD</b>

Precio: <b>{sell_info['price']}</b>
RSI: {sell_info['rsi']}
ADX: {sell_info['adx']}

📌 <b>Configuración recomendada:</b>
• Lote: <b>0.10 Cent</b>
• Stop Loss: 500 pips (-50.00)
• Take Profit: 160 pips (+16.00)

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
                send_alert(msg)
                last_alert_time = time.time()

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Error en el loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main_loop()
