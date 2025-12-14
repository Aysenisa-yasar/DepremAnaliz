# app.py
# Bu dosya, YZ modelini çalıştıracak olan Python arka ucudur (Backend).

import os # Ortam değişkenlerini okumak için eklendi
import time
import requests
import numpy as np
import math 
import json
import pickle
from datetime import datetime, timedelta
from collections import deque

from flask import Flask, jsonify, request
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb
from flask_cors import CORS 
from threading import Thread
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import requests.exceptions
import pandas as pd 

# --- FLASK UYGULAMASI VE AYARLARI ---
app = Flask(__name__)

# CORS ayarları - GitHub Pages ve Render.com için
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://aysenisa-yasar.github.io",
            "https://depremanaliz.onrender.com",
            "http://localhost:5000",
            "http://localhost:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:3000"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
}) 

# Kandilli verilerini çeken üçüncü taraf API
KANDILLI_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'

# API veri cache (son 5 dakika)
api_cache = {'data': None, 'timestamp': 0, 'cache_duration': 300}  # 5 dakika cache

def fetch_earthquake_data_with_retry(url, max_retries=2, timeout=60):
    """API'den veri çeker, retry mekanizması ve cache ile."""
    global api_cache
    
    # Cache kontrolü (son 5 dakika içinde çekilen veriyi kullan)
    current_time = time.time()
    if api_cache['data'] and (current_time - api_cache['timestamp']) < api_cache['cache_duration']:
        print(f"[CACHE] Önbellekten veri döndürülüyor ({(current_time - api_cache['timestamp']):.0f} saniye önce)")
        return api_cache['data']
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            })
            response.raise_for_status()
            data = response.json().get('result', [])
            
            # Cache'e kaydet
            api_cache['data'] = data
            api_cache['timestamp'] = current_time
            
            return data
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = 2
                print(f"[RETRY] API timeout, {wait_time} saniye bekleyip tekrar deneniyor... (Deneme {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print("[ERROR] API timeout: Tüm denemeler başarısız")
                # Cache'deki eski veriyi döndür (varsa)
                if api_cache['data']:
                    print("[CACHE] Eski cache verisi döndürülüyor")
                    return api_cache['data']
                return []
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2
                print(f"[RETRY] API hatası: {e}, {wait_time} saniye bekleyip tekrar deneniyor...")
                time.sleep(wait_time)
                continue
            else:
                print(f"[ERROR] API hatası: Tüm denemeler başarısız - {e}")
                # Cache'deki eski veriyi döndür (varsa)
                if api_cache['data']:
                    print("[CACHE] Eski cache verisi döndürülüyor")
                    return api_cache['data']
                return []
    return []

# --- TWILIO BİLDİRİM SABİTLERİ (ORTAM DEĞİŞKENLERİNDEN OKUNUR) ---
# Twilio kimlik bilgileri ve numarası, Render ortam değişkenlerinden alınır.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER")

# --- KULLANICI AYARLARI (KALICI HAFIZA - JSON DOSYASI) ---
USER_DATA_FILE = 'user_alerts.json'
last_big_earthquake = {'mag': 0, 'time': 0}

def load_user_alerts():
    """ Kullanıcı konum bilgilerini JSON dosyasından yükler. """
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Kullanıcı verileri yüklenirken hata: {e}")
    return {}

def save_user_alerts(user_alerts):
    """ Kullanıcı konum bilgilerini JSON dosyasına kaydeder. """
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_alerts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Kullanıcı verileri kaydedilirken hata: {e}")

# Başlangıçta kullanıcı verilerini yükle
user_alerts = load_user_alerts()

# --- GELİŞMİŞ MAKİNE ÖĞRENMESİ MODELLERİ ---
EARTHQUAKE_HISTORY_FILE = 'earthquake_history.json'
MODEL_DIR = 'ml_models'
ISTANBUL_ALERT_HISTORY = deque(maxlen=1000)  # Son 1000 deprem verisi

# Model dosyaları
RISK_PREDICTION_MODEL_FILE = f'{MODEL_DIR}/risk_prediction_model.pkl'
ISTANBUL_EARLY_WARNING_MODEL_FILE = f'{MODEL_DIR}/istanbul_early_warning_model.pkl'
ANOMALY_DETECTION_MODEL_FILE = f'{MODEL_DIR}/anomaly_detection_model.pkl'

# Model dosyalarını oluştur
os.makedirs(MODEL_DIR, exist_ok=True)

# İstanbul koordinatları
ISTANBUL_COORDS = {"lat": 41.0082, "lon": 28.9784}
ISTANBUL_RADIUS = 200  # km - İstanbul için izleme yarıçapı

# --- TÜRKİYE AKTİF FAY HATLARI VERİSİ ---
TURKEY_FAULT_LINES = [
    {"name": "Kuzey Anadolu Fay Hattı (KAF)", "coords": [
        [40.0, 26.0], [40.2, 27.0], [40.5, 28.0], [40.7, 29.0], 
        [40.9, 30.0], [41.0, 31.0], [41.2, 32.0], [41.4, 33.0],
        [41.6, 34.0], [41.8, 35.0], [42.0, 36.0], [42.2, 37.0]
    ]},
    {"name": "Doğu Anadolu Fay Hattı (DAF)", "coords": [
        [37.0, 38.0], [37.5, 39.0], [38.0, 40.0], [38.5, 41.0],
        [39.0, 42.0], [39.5, 43.0], [40.0, 44.0]
    ]},
    {"name": "Ege Graben Sistemi", "coords": [
        [38.0, 26.0], [38.5, 27.0], [39.0, 28.0], [39.5, 29.0]
    ]},
    {"name": "Batı Anadolu Fay Sistemi", "coords": [
        [38.5, 27.0], [39.0, 28.5], [39.5, 30.0], [40.0, 31.5]
    ]}
]

# --- TÜRKİYE İLLERİ VE BİNA YAPISI VERİLERİ ---
# Her il için: koordinatlar, bina yapısı dağılımı (güçlendirilmiş, normal, zayıf yüzdesi)
TURKEY_CITIES = {
    "İstanbul": {"lat": 41.0082, "lon": 28.9784, "building_structure": {"reinforced": 0.35, "normal": 0.50, "weak": 0.15}},
    "Ankara": {"lat": 39.9334, "lon": 32.8597, "building_structure": {"reinforced": 0.40, "normal": 0.45, "weak": 0.15}},
    "İzmir": {"lat": 38.4237, "lon": 27.1428, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Bursa": {"lat": 40.1826, "lon": 29.0665, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Antalya": {"lat": 36.8969, "lon": 30.7133, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Adana": {"lat": 36.9914, "lon": 35.3308, "building_structure": {"reinforced": 0.20, "normal": 0.60, "weak": 0.20}},
    "Konya": {"lat": 37.8746, "lon": 32.4932, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Gaziantep": {"lat": 37.0662, "lon": 37.3833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Şanlıurfa": {"lat": 37.1674, "lon": 38.7955, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kocaeli": {"lat": 40.8533, "lon": 29.8815, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Kayseri": {"lat": 38.7312, "lon": 35.4787, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Eskişehir": {"lat": 39.7767, "lon": 30.5206, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Diyarbakır": {"lat": 37.9144, "lon": 40.2306, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Samsun": {"lat": 41.2867, "lon": 36.3300, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Denizli": {"lat": 37.7765, "lon": 29.0864, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kahramanmaraş": {"lat": 37.5858, "lon": 36.9371, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Malatya": {"lat": 38.3552, "lon": 38.3095, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Van": {"lat": 38.4891, "lon": 43.4089, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Erzurum": {"lat": 39.9043, "lon": 41.2679, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Batman": {"lat": 37.8812, "lon": 41.1351, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Elazığ": {"lat": 38.6748, "lon": 39.2225, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Hatay": {"lat": 36.4018, "lon": 36.3498, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Manisa": {"lat": 38.6191, "lon": 27.4289, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Sivas": {"lat": 39.7477, "lon": 37.0179, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Balıkesir": {"lat": 39.6484, "lon": 27.8826, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Trabzon": {"lat": 41.0015, "lon": 39.7178, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Ordu": {"lat": 40.9839, "lon": 37.8764, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Afyonkarahisar": {"lat": 38.7638, "lon": 30.5403, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Aydın": {"lat": 37.8444, "lon": 27.8458, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Muğla": {"lat": 37.2153, "lon": 28.3636, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Tekirdağ": {"lat": 40.9833, "lon": 27.5167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Sakarya": {"lat": 40.7569, "lon": 30.3781, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Mersin": {"lat": 36.8000, "lon": 34.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Zonguldak": {"lat": 41.4564, "lon": 31.7987, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kütahya": {"lat": 39.4167, "lon": 29.9833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Osmaniye": {"lat": 37.0742, "lon": 36.2478, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Çorum": {"lat": 40.5506, "lon": 34.9556, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Edirne": {"lat": 41.6772, "lon": 26.5556, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Giresun": {"lat": 40.9128, "lon": 38.3895, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Aksaray": {"lat": 38.3686, "lon": 34.0364, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Niğde": {"lat": 37.9667, "lon": 34.6833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Nevşehir": {"lat": 38.6244, "lon": 34.7239, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Bolu": {"lat": 40.7333, "lon": 31.6000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Yozgat": {"lat": 39.8200, "lon": 34.8044, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Düzce": {"lat": 40.8439, "lon": 31.1565, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bingöl": {"lat": 38.8847, "lon": 40.4981, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Bitlis": {"lat": 38.4000, "lon": 42.1000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Muş": {"lat": 38.7333, "lon": 41.4833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Hakkari": {"lat": 37.5744, "lon": 43.7408, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Siirt": {"lat": 37.9333, "lon": 41.9500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Şırnak": {"lat": 37.5167, "lon": 42.4500, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Iğdır": {"lat": 39.9167, "lon": 44.0333, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Ardahan": {"lat": 41.1167, "lon": 42.7000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Artvin": {"lat": 41.1833, "lon": 41.8167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Rize": {"lat": 41.0201, "lon": 40.5234, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Gümüşhane": {"lat": 40.4603, "lon": 39.5081, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Bayburt": {"lat": 40.2553, "lon": 40.2247, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Erzincan": {"lat": 39.7500, "lon": 39.5000, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Tunceli": {"lat": 39.1083, "lon": 39.5333, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Adıyaman": {"lat": 37.7639, "lon": 38.2789, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kilis": {"lat": 36.7167, "lon": 37.1167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Kırıkkale": {"lat": 39.8333, "lon": 33.5000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kırşehir": {"lat": 39.1500, "lon": 34.1667, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Karabük": {"lat": 41.2000, "lon": 32.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bartın": {"lat": 41.6333, "lon": 32.3333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kastamonu": {"lat": 41.3667, "lon": 33.7667, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Sinop": {"lat": 42.0167, "lon": 35.1500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Çanakkale": {"lat": 40.1553, "lon": 26.4142, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Bilecik": {"lat": 40.1419, "lon": 29.9792, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Burdur": {"lat": 37.7167, "lon": 30.2833, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Isparta": {"lat": 37.7667, "lon": 30.5500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Uşak": {"lat": 38.6833, "lon": 29.4000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kırklareli": {"lat": 41.7333, "lon": 27.2167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Yalova": {"lat": 40.6500, "lon": 29.2667, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Karabük": {"lat": 41.2000, "lon": 32.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kars": {"lat": 40.6000, "lon": 43.0833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Ağrı": {"lat": 39.7167, "lon": 43.0500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Amasya": {"lat": 40.6500, "lon": 35.8333, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Tokat": {"lat": 40.3167, "lon": 36.5500, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Sivas": {"lat": 39.7477, "lon": 37.0179, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Ordu": {"lat": 40.9839, "lon": 37.8764, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Giresun": {"lat": 40.9128, "lon": 38.3895, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Trabzon": {"lat": 41.0015, "lon": 39.7178, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Rize": {"lat": 41.0201, "lon": 40.5234, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Artvin": {"lat": 41.1833, "lon": 41.8167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Ardahan": {"lat": 41.1167, "lon": 42.7000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Iğdır": {"lat": 39.9167, "lon": 44.0333, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kars": {"lat": 40.6000, "lon": 43.0833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Ağrı": {"lat": 39.7167, "lon": 43.0500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Muş": {"lat": 38.7333, "lon": 41.4833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Bitlis": {"lat": 38.4000, "lon": 42.1000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Van": {"lat": 38.4891, "lon": 43.4089, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Hakkari": {"lat": 37.5744, "lon": 43.7408, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Şırnak": {"lat": 37.5167, "lon": 42.4500, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Siirt": {"lat": 37.9333, "lon": 41.9500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Batman": {"lat": 37.8812, "lon": 41.1351, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Diyarbakır": {"lat": 37.9144, "lon": 40.2306, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Mardin": {"lat": 37.3131, "lon": 40.7356, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Şanlıurfa": {"lat": 37.1674, "lon": 38.7955, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Gaziantep": {"lat": 37.0662, "lon": 37.3833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Kilis": {"lat": 36.7167, "lon": 37.1167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Adıyaman": {"lat": 37.7639, "lon": 38.2789, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kahramanmaraş": {"lat": 37.5858, "lon": 36.9371, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Osmaniye": {"lat": 37.0742, "lon": 36.2478, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Hatay": {"lat": 36.4018, "lon": 36.3498, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Adana": {"lat": 36.9914, "lon": 35.3308, "building_structure": {"reinforced": 0.20, "normal": 0.60, "weak": 0.20}},
    "Mersin": {"lat": 36.8000, "lon": 34.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Antalya": {"lat": 36.8969, "lon": 30.7133, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Burdur": {"lat": 37.7167, "lon": 30.2833, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Isparta": {"lat": 37.7667, "lon": 30.5500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Afyonkarahisar": {"lat": 38.7638, "lon": 30.5403, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Kütahya": {"lat": 39.4167, "lon": 29.9833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Uşak": {"lat": 38.6833, "lon": 29.4000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Manisa": {"lat": 38.6191, "lon": 27.4289, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "İzmir": {"lat": 38.4237, "lon": 27.1428, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Aydın": {"lat": 37.8444, "lon": 27.8458, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Muğla": {"lat": 37.2153, "lon": 28.3636, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Denizli": {"lat": 37.7765, "lon": 29.0864, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bursa": {"lat": 40.1826, "lon": 29.0665, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Balıkesir": {"lat": 39.6484, "lon": 27.8826, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Çanakkale": {"lat": 40.1553, "lon": 26.4142, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Tekirdağ": {"lat": 40.9833, "lon": 27.5167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Edirne": {"lat": 41.6772, "lon": 26.5556, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Kırklareli": {"lat": 41.7333, "lon": 27.2167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "İstanbul": {"lat": 41.0082, "lon": 28.9784, "building_structure": {"reinforced": 0.35, "normal": 0.50, "weak": 0.15}},
    "Kocaeli": {"lat": 40.8533, "lon": 29.8815, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Sakarya": {"lat": 40.7569, "lon": 30.3781, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Düzce": {"lat": 40.8439, "lon": 31.1565, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bolu": {"lat": 40.7333, "lon": 31.6000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bilecik": {"lat": 40.1419, "lon": 29.9792, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Eskişehir": {"lat": 39.7767, "lon": 30.5206, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Ankara": {"lat": 39.9334, "lon": 32.8597, "building_structure": {"reinforced": 0.40, "normal": 0.45, "weak": 0.15}},
    "Kırıkkale": {"lat": 39.8333, "lon": 33.5000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kırşehir": {"lat": 39.1500, "lon": 34.1667, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Nevşehir": {"lat": 38.6244, "lon": 34.7239, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Aksaray": {"lat": 38.3686, "lon": 34.0364, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Niğde": {"lat": 37.9667, "lon": 34.6833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Konya": {"lat": 37.8746, "lon": 32.4932, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Karaman": {"lat": 37.1811, "lon": 33.2150, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Mersin": {"lat": 36.8000, "lon": 34.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kastamonu": {"lat": 41.3667, "lon": 33.7667, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Sinop": {"lat": 42.0167, "lon": 35.1500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Çorum": {"lat": 40.5506, "lon": 34.9556, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Amasya": {"lat": 40.6500, "lon": 35.8333, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Samsun": {"lat": 41.2867, "lon": 36.3300, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Ordu": {"lat": 40.9839, "lon": 37.8764, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Giresun": {"lat": 40.9128, "lon": 38.3895, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Trabzon": {"lat": 41.0015, "lon": 39.7178, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Rize": {"lat": 41.0201, "lon": 40.5234, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Artvin": {"lat": 41.1833, "lon": 41.8167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Ardahan": {"lat": 41.1167, "lon": 42.7000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Iğdır": {"lat": 39.9167, "lon": 44.0333, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kars": {"lat": 40.6000, "lon": 43.0833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Ağrı": {"lat": 39.7167, "lon": 43.0500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Muş": {"lat": 38.7333, "lon": 41.4833, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Bitlis": {"lat": 38.4000, "lon": 42.1000, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Van": {"lat": 38.4891, "lon": 43.4089, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Hakkari": {"lat": 37.5744, "lon": 43.7408, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Şırnak": {"lat": 37.5167, "lon": 42.4500, "building_structure": {"reinforced": 0.10, "normal": 0.45, "weak": 0.45}},
    "Siirt": {"lat": 37.9333, "lon": 41.9500, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Batman": {"lat": 37.8812, "lon": 41.1351, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Diyarbakır": {"lat": 37.9144, "lon": 40.2306, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Mardin": {"lat": 37.3131, "lon": 40.7356, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Şanlıurfa": {"lat": 37.1674, "lon": 38.7955, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Gaziantep": {"lat": 37.0662, "lon": 37.3833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Kilis": {"lat": 36.7167, "lon": 37.1167, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Adıyaman": {"lat": 37.7639, "lon": 38.2789, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Kahramanmaraş": {"lat": 37.5858, "lon": 36.9371, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Osmaniye": {"lat": 37.0742, "lon": 36.2478, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Hatay": {"lat": 36.4018, "lon": 36.3498, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Adana": {"lat": 36.9914, "lon": 35.3308, "building_structure": {"reinforced": 0.20, "normal": 0.60, "weak": 0.20}},
    "Mersin": {"lat": 36.8000, "lon": 34.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Antalya": {"lat": 36.8969, "lon": 30.7133, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Burdur": {"lat": 37.7167, "lon": 30.2833, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Isparta": {"lat": 37.7667, "lon": 30.5500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Afyonkarahisar": {"lat": 38.7638, "lon": 30.5403, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Kütahya": {"lat": 39.4167, "lon": 29.9833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Uşak": {"lat": 38.6833, "lon": 29.4000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Manisa": {"lat": 38.6191, "lon": 27.4289, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "İzmir": {"lat": 38.4237, "lon": 27.1428, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Aydın": {"lat": 37.8444, "lon": 27.8458, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Muğla": {"lat": 37.2153, "lon": 28.3636, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Denizli": {"lat": 37.7765, "lon": 29.0864, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bursa": {"lat": 40.1826, "lon": 29.0665, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Balıkesir": {"lat": 39.6484, "lon": 27.8826, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Çanakkale": {"lat": 40.1553, "lon": 26.4142, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Tekirdağ": {"lat": 40.9833, "lon": 27.5167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Edirne": {"lat": 41.6772, "lon": 26.5556, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Kırklareli": {"lat": 41.7333, "lon": 27.2167, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "İstanbul": {"lat": 41.0082, "lon": 28.9784, "building_structure": {"reinforced": 0.35, "normal": 0.50, "weak": 0.15}},
    "Kocaeli": {"lat": 40.8533, "lon": 29.8815, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Sakarya": {"lat": 40.7569, "lon": 30.3781, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Düzce": {"lat": 40.8439, "lon": 31.1565, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bolu": {"lat": 40.7333, "lon": 31.6000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bilecik": {"lat": 40.1419, "lon": 29.9792, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Eskişehir": {"lat": 39.7767, "lon": 30.5206, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Ankara": {"lat": 39.9334, "lon": 32.8597, "building_structure": {"reinforced": 0.40, "normal": 0.45, "weak": 0.15}},
    "Kırıkkale": {"lat": 39.8333, "lon": 33.5000, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kırşehir": {"lat": 39.1500, "lon": 34.1667, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Nevşehir": {"lat": 38.6244, "lon": 34.7239, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Aksaray": {"lat": 38.3686, "lon": 34.0364, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Niğde": {"lat": 37.9667, "lon": 34.6833, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Konya": {"lat": 37.8746, "lon": 32.4932, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Karaman": {"lat": 37.1811, "lon": 33.2150, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Mersin": {"lat": 36.8000, "lon": 34.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Kastamonu": {"lat": 41.3667, "lon": 33.7667, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Sinop": {"lat": 42.0167, "lon": 35.1500, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Çorum": {"lat": 40.5506, "lon": 34.9556, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Amasya": {"lat": 40.6500, "lon": 35.8333, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Sivas": {"lat": 39.7477, "lon": 37.0179, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Tokat": {"lat": 40.3167, "lon": 36.5500, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Erzincan": {"lat": 39.7500, "lon": 39.5000, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Tunceli": {"lat": 39.1083, "lon": 39.5333, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Elazığ": {"lat": 38.6748, "lon": 39.2225, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Malatya": {"lat": 38.3552, "lon": 38.3095, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Erzurum": {"lat": 39.9043, "lon": 41.2679, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Bingöl": {"lat": 38.8847, "lon": 40.4981, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Gümüşhane": {"lat": 40.4603, "lon": 39.5081, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Bayburt": {"lat": 40.2553, "lon": 40.2247, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Yozgat": {"lat": 39.8200, "lon": 34.8044, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}},
    "Zonguldak": {"lat": 41.4564, "lon": 31.7987, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Karabük": {"lat": 41.2000, "lon": 32.6333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Bartın": {"lat": 41.6333, "lon": 32.3333, "building_structure": {"reinforced": 0.25, "normal": 0.60, "weak": 0.15}},
    "Yalova": {"lat": 40.6500, "lon": 29.2667, "building_structure": {"reinforced": 0.30, "normal": 0.55, "weak": 0.15}},
    "Mardin": {"lat": 37.3131, "lon": 40.7356, "building_structure": {"reinforced": 0.15, "normal": 0.50, "weak": 0.35}},
    "Karaman": {"lat": 37.1811, "lon": 33.2150, "building_structure": {"reinforced": 0.20, "normal": 0.55, "weak": 0.25}}
} 


# --- YARDIMCI FONKSİYONLAR ---

def send_whatsapp_notification(recipient_number, body, location_url=None):
    """ Twilio üzerinden WhatsApp mesajı gönderir. Konum linki eklenebilir. 
    Returns: (success: bool, error_message: str veya None)
    """
    # Twilio bilgileri kontrolü
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        print("[WARNING] Twilio ayarlari yapilmamis! Ortam degiskenlerini kontrol edin.")
        print("  Gerekli: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER")
        return False, "Twilio ayarları yapılmamış"
    
    # Sandbox kontrolü - Eğer sandbox numarası kullanılıyorsa uyarı ver
    is_sandbox = '14155238886' in TWILIO_WHATSAPP_NUMBER or 'sandbox' in TWILIO_WHATSAPP_NUMBER.lower()
    if is_sandbox:
        print(f"[INFO] Twilio WhatsApp Sandbox modu aktif. Sadece sandbox'a kayıtlı numaralara mesaj gönderilebilir.")
        print(f"[INFO] Numara {recipient_number} sandbox'a kayıtlı değilse mesaj gönderilemez.")
        print(f"[INFO] Çözüm: Twilio Console > Messaging > WhatsApp Sandbox sayfasından 'join code' ile numarayı ekleyin.")
        print(f"[INFO] Production moduna geçmek için: TWILIO_PRODUCTION_KURULUM.md dosyasına bakın.")
    else:
        print(f"[INFO] Twilio WhatsApp Production modu aktif. Tüm numaralara mesaj gönderilebilir.")
    
    try:
        # Client, Ortam Değişkenlerinden alınan SID ve Token ile başlatılır
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Numara formatını düzelt (ülke kodu ile başlamalı)
        if not recipient_number.startswith('+'):
            recipient_number = '+' + recipient_number.lstrip('0')
        
        whatsapp_number = f"whatsapp:{recipient_number}"
        
        # Konum linki varsa mesaja ekle
        if location_url:
            body += f"\n\nKonum: {location_url}"
        
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=body,
            to=whatsapp_number
        )
        print(f"[OK] WhatsApp bildirimi gonderildi. SID: {message.sid}")
        return True, None
    except TwilioRestException as e:
        error_msg = str(e)
        error_code = e.code if hasattr(e, 'code') else None
        status_code = e.status if hasattr(e, 'status') else None
        
        print(f"[ERROR] Twilio hatası: {error_msg} (Code: {error_code}, Status: {status_code})")
        
        # HTTP 429 - Rate Limit hatası
        if status_code == 429 or error_code == 20429 or "429" in error_msg or "daily messages limit" in error_msg.lower() or "exceeded" in error_msg.lower():
            limit_info = "50 mesaj/gün" if "50" in error_msg else "günlük mesaj limiti"
            error_message = f"HTTP 429 error: Twilio hesabınızın {limit_info} aşıldı. Limit yarın sıfırlanacak. Lütfen daha sonra tekrar deneyin."
            print(f"[RATE LIMIT] {error_message}")
            return False, error_message
        
        # Diğer hata türleri
        if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
            print("[NOT] Twilio hesap bilgileri hatali olabilir. Kontrol edin:")
            print("  - Account SID dogru mu?")
            print("  - Auth Token dogru mu?")
            print("  - WhatsApp numarasi dogru formatta mi? (whatsapp:+14155238886)")
            return False, "Twilio hesap bilgileri hatalı olabilir"
        elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
            print("[NOT] Twilio hesabinizda yetki sorunu var.")
            print("  - Hesabiniz aktif mi?")
            print("  - WhatsApp Sandbox'a katildiniz mi?")
            return False, "Twilio hesabınızda yetki sorunu var"
        elif "not a valid" in error_msg.lower() or "format" in error_msg.lower():
            print("[NOT] Telefon numarasi format hatasi.")
            print("  - Numara ulke kodu ile baslamali (ornek: +905551234567)")
            print("  - WhatsApp Sandbox'a kayitli numara olmali")
            return False, "Telefon numarası formatı hatalı"
        
        return False, f"Twilio hatası: {error_msg}"
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] WhatsApp mesaji gonderilemedi: {error_msg}")
        return False, f"Beklenmeyen hata: {error_msg}"

# ... (haversine ve calculate_clustering_risk fonksiyonları aynı kalır)

def haversine(lat1, lon1, lat2, lon2):
    """ İki nokta arasındaki mesafeyi kilometre cinsinden hesaplar. """
    R = 6371 
    
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    distance = R * c
    return distance

def calculate_clustering_risk(earthquakes):
    """ K-Means kümeleme algoritması kullanarak risk bölgelerini tespit eder. """
    
    if not earthquakes or len(earthquakes) == 0:
        return {"status": "low_activity", "risk_regions": []}
    
    coords = []
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            mag = eq.get('mag', 0) 
            coords.append([lon, lat, mag])
    
    if len(coords) < 10: 
        return {"status": "low_activity", "risk_regions": []}

    X = np.array(coords)
    NUM_CLUSTERS = min(5, len(coords) // 2)
    
    try:
        kmeans = KMeans(n_clusters=NUM_CLUSTERS, random_state=42, n_init=10)
        kmeans.fit(X)
    except ValueError as e:
        print(f"K-Means Hatası: {e}")
        return {"status": "error", "message": "Kümeleme modelinde bir hata oluştu."}

    risk_regions = []
    
    for i, center in enumerate(kmeans.cluster_centers_):
        cluster_points = X[kmeans.labels_ == i]
        avg_mag = np.mean(cluster_points[:, 2])
        density_factor = len(cluster_points) / len(earthquakes) 
        risk_score = min(10, round(avg_mag * 2 + density_factor * 10, 1))
        
        risk_regions.append({
            "id": i,
            "lon": center[0],
            "lat": center[1],
            "score": risk_score,
            "density": len(cluster_points)
        })

    return {"status": "success", "risk_regions": risk_regions}

# --- GELİŞMİŞ MAKİNE ÖĞRENMESİ FONKSİYONLARI ---

def extract_features(earthquakes, target_lat, target_lon, time_window_hours=24):
    """
    Deprem verilerinden gelişmiş özellikler çıkarır (Feature Engineering).
    """
    features = {}
    
    if not earthquakes:
        return None
    
    # Zaman penceresi içindeki depremleri filtrele
    current_time = datetime.now()
    window_start = current_time - timedelta(hours=time_window_hours)
    
    recent_eqs = []
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            mag = eq.get('mag', 0)
            distance = haversine(target_lat, target_lon, lat, lon)
            
            if distance < 300 and mag >= 2.0:
                recent_eqs.append({
                    'mag': mag,
                    'distance': distance,
                    'depth': eq.get('depth', 10),
                    'lat': lat,
                    'lon': lon,
                    'timestamp': eq.get('timestamp', time.time())
                })
    
    # Veri yoksa bile temel özellikler döndür (fay hattı mesafesi, genel aktivite vb.)
    if len(recent_eqs) == 0:
        # Tüm depremleri kontrol et (mesafe filtresi olmadan)
        all_eqs = []
        for eq in earthquakes:
            if eq.get('geojson') and eq['geojson'].get('coordinates'):
                lon, lat = eq['geojson']['coordinates']
                mag = eq.get('mag', 0)
                distance = haversine(target_lat, target_lon, lat, lon)
                if mag >= 2.0:
                    all_eqs.append({
                        'mag': mag,
                        'distance': distance,
                        'depth': eq.get('depth', 10),
                        'lat': lat,
                        'lon': lon,
                        'timestamp': eq.get('timestamp', time.time())
                    })
        
        # Eğer hiç deprem yoksa bile temel özellikler döndür
        if len(all_eqs) == 0:
            # Sadece fay hattı mesafesi ve genel bilgiler
            nearest_fault_distance = float('inf')
            for fault in TURKEY_FAULT_LINES:
                for coord in fault['coords']:
                    fault_lat, fault_lon = coord
                    dist = haversine(target_lat, target_lon, fault_lat, fault_lon)
                    nearest_fault_distance = min(nearest_fault_distance, dist)
            
            return {
                'count': 0,
                'max_magnitude': 0,
                'mean_magnitude': 0,
                'std_magnitude': 0,
                'min_distance': 300,
                'mean_distance': 300,
                'mean_depth': 10,
                'mean_interval': 3600,
                'min_interval': 3600,
                'mag_above_4': 0,
                'mag_above_5': 0,
                'mag_above_6': 0,
                'within_50km': 0,
                'within_100km': 0,
                'within_150km': 0,
                'nearest_fault_distance': nearest_fault_distance,
                'activity_density': 0,
                'magnitude_distance_ratio': 0,
                'magnitude_trend': 0
            }
        
        # Tüm depremleri kullan (mesafe filtresi yok)
        recent_eqs = all_eqs
    
    # Temel istatistikler
    magnitudes = [eq['mag'] for eq in recent_eqs]
    distances = [eq['distance'] for eq in recent_eqs]
    depths = [eq['depth'] for eq in recent_eqs]
    
    features['count'] = len(recent_eqs)
    features['max_magnitude'] = max(magnitudes) if magnitudes else 0
    features['mean_magnitude'] = np.mean(magnitudes) if magnitudes else 0
    features['std_magnitude'] = np.std(magnitudes) if magnitudes else 0
    features['min_distance'] = min(distances) if distances else 300
    features['mean_distance'] = np.mean(distances) if distances else 300
    features['mean_depth'] = np.mean(depths) if depths else 10
    
    # Zaman bazlı özellikler
    if len(recent_eqs) > 1:
        timestamps = sorted([eq['timestamp'] for eq in recent_eqs])
        time_intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        features['mean_interval'] = np.mean(time_intervals) if time_intervals else 3600
        features['min_interval'] = min(time_intervals) if time_intervals else 3600
    else:
        features['mean_interval'] = 3600
        features['min_interval'] = 3600
    
    # Büyüklük dağılımı
    features['mag_above_4'] = sum(1 for m in magnitudes if m >= 4.0)
    features['mag_above_5'] = sum(1 for m in magnitudes if m >= 5.0)
    features['mag_above_6'] = sum(1 for m in magnitudes if m >= 6.0)
    
    # Mesafe dağılımı
    features['within_50km'] = sum(1 for d in distances if d <= 50)
    features['within_100km'] = sum(1 for d in distances if d <= 100)
    features['within_150km'] = sum(1 for d in distances if d <= 150)
    
    # Derinlik dağılımı
    features['shallow_quakes'] = sum(1 for d in depths if d <= 10)
    features['deep_quakes'] = sum(1 for d in depths if d > 30)
    
    # Fay hattı yakınlığı
    nearest_fault = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            fault_lat, fault_lon = coord
            dist = haversine(target_lat, target_lon, fault_lat, fault_lon)
            nearest_fault = min(nearest_fault, dist)
    features['nearest_fault_distance'] = nearest_fault
    
    # Aktivite yoğunluğu (deprem/km²)
    if features['mean_distance'] > 0:
        features['activity_density'] = features['count'] / (np.pi * (features['mean_distance'] ** 2))
    else:
        features['activity_density'] = 0
    
    # Büyüklük-mesafe etkileşimi
    features['magnitude_distance_ratio'] = features['max_magnitude'] / (features['min_distance'] + 1)
    
    # Zaman trendi (son depremlerin büyüklüğü artıyor mu?)
    if len(recent_eqs) >= 3:
        sorted_by_time = sorted(recent_eqs, key=lambda x: x['timestamp'])
        first_half = sorted_by_time[:len(sorted_by_time)//2]
        second_half = sorted_by_time[len(sorted_by_time)//2:]
        first_avg_mag = np.mean([eq['mag'] for eq in first_half])
        second_avg_mag = np.mean([eq['mag'] for eq in second_half])
        features['magnitude_trend'] = second_avg_mag - first_avg_mag
    else:
        features['magnitude_trend'] = 0
    
    return features

def train_risk_prediction_model(earthquake_history):
    """
    Gelişmiş risk tahmin modeli eğitir (Ensemble: Random Forest + XGBoost + LightGBM).
    """
    if not earthquake_history or len(earthquake_history) < 50:
        print("Yeterli eğitim verisi yok, model eğitilemiyor.")
        return None
    
    # Veriyi hazırla
    X = []
    y = []
    
    for record in earthquake_history:
        if 'features' in record and 'risk_score' in record:
            features = record['features']
            risk = record['risk_score']
            
            # Feature vektörü oluştur
            feature_vector = [
                features.get('count', 0),
                features.get('max_magnitude', 0),
                features.get('mean_magnitude', 0),
                features.get('std_magnitude', 0),
                features.get('min_distance', 300),
                features.get('mean_distance', 300),
                features.get('mean_depth', 10),
                features.get('mean_interval', 3600),
                features.get('min_interval', 3600),
                features.get('mag_above_4', 0),
                features.get('mag_above_5', 0),
                features.get('within_50km', 0),
                features.get('within_100km', 0),
                features.get('nearest_fault_distance', 200),
                features.get('activity_density', 0),
                features.get('magnitude_distance_ratio', 0),
                features.get('magnitude_trend', 0)
            ]
            
            X.append(feature_vector)
            y.append(risk)
    
    if len(X) < 20:
        return None
    
    X = np.array(X)
    y = np.array(y)
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Ensemble modeller
    models = {
        'random_forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
        'xgboost': xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42),
        'lightgbm': lgb.LGBMRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
    }
    
    trained_models = {}
    predictions = {}
    
    for name, model in models.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        mse = mean_squared_error(y_test, pred)
        r2 = r2_score(y_test, pred)
        print(f"{name} - MSE: {mse:.4f}, R²: {r2:.4f}")
        trained_models[name] = model
        predictions[name] = pred
    
    # Ensemble tahmin (ağırlıklı ortalama)
    ensemble_pred = (
        0.4 * predictions['random_forest'] +
        0.35 * predictions['xgboost'] +
        0.25 * predictions['lightgbm']
    )
    ensemble_mse = mean_squared_error(y_test, ensemble_pred)
    ensemble_r2 = r2_score(y_test, ensemble_pred)
    print(f"Ensemble - MSE: {ensemble_mse:.4f}, R²: {ensemble_r2:.4f}")
    
    # Modeli kaydet
    try:
        os.makedirs(os.path.dirname(RISK_PREDICTION_MODEL_FILE), exist_ok=True)
        with open(RISK_PREDICTION_MODEL_FILE, 'wb') as f:
            pickle.dump(trained_models, f)
        print("[OK] Risk tahmin modeli kaydedildi.")
    except Exception as e:
        print(f"Model kaydedilemedi: {e}")
    
    return trained_models

def predict_risk_with_ml(earthquakes, target_lat, target_lon):
    """
    Gelişmiş ML modeli ile risk tahmini yapar.
    """
    # Özellik çıkarımı (artık her zaman özellik döndürür, None döndürmez)
    features = extract_features(earthquakes, target_lat, target_lon)
    
    if features is None:
        # Bu durumda geleneksel yönteme fallback
        return predict_earthquake_risk(earthquakes, target_lat, target_lon)
    
    # Model yükle
    try:
        if os.path.exists(RISK_PREDICTION_MODEL_FILE):
            with open(RISK_PREDICTION_MODEL_FILE, 'rb') as f:
                model_data = pickle.load(f)
            
            # Yeni format (optimize edilmiş) veya eski format kontrolü
            if isinstance(model_data, dict) and 'models' in model_data:
                models = model_data['models']
                weights = model_data.get('weights', {'random_forest': 0.4, 'xgboost': 0.35, 'lightgbm': 0.25})
            else:
                # Eski format (direkt modeller)
                models = model_data
                weights = {'random_forest': 0.4, 'xgboost': 0.35, 'lightgbm': 0.25}
        else:
            # Model yoksa geleneksel yönteme fallback
            return predict_earthquake_risk(earthquakes, target_lat, target_lon)
    except Exception as e:
        print(f"Model yüklenemedi: {e}")
        return {"risk_level": "Düşük", "risk_score": 2.0, "method": "fallback", "reason": "Model hatası"}
    
    # Feature vektörü oluştur
    feature_vector = np.array([[
        features.get('count', 0),
        features.get('max_magnitude', 0),
        features.get('mean_magnitude', 0),
        features.get('std_magnitude', 0),
        features.get('min_distance', 300),
        features.get('mean_distance', 300),
        features.get('mean_depth', 10),
        features.get('mean_interval', 3600),
        features.get('min_interval', 3600),
        features.get('mag_above_4', 0),
        features.get('mag_above_5', 0),
        features.get('within_50km', 0),
        features.get('within_100km', 0),
        features.get('nearest_fault_distance', 200),
        features.get('activity_density', 0),
        features.get('magnitude_distance_ratio', 0),
        features.get('magnitude_trend', 0)
    ]])
    
    # Ensemble tahmin (ağırlıklı)
    rf_pred = models['random_forest'].predict(feature_vector)[0]
    xgb_pred = models['xgboost'].predict(feature_vector)[0]
    lgb_pred = models['lightgbm'].predict(feature_vector)[0]
    
    risk_score = weights.get('random_forest', 0.4) * rf_pred + weights.get('xgboost', 0.35) * xgb_pred + weights.get('lightgbm', 0.25) * lgb_pred
    risk_score = max(0, min(10, risk_score))  # 0-10 arası sınırla
    
    # Risk seviyesi
    if risk_score >= 7.5:
        level = "Çok Yüksek"
    elif risk_score >= 5.5:
        level = "Yüksek"
    elif risk_score >= 3.5:
        level = "Orta"
    else:
        level = "Düşük"
    
    return {
        "risk_level": level,
        "risk_score": round(risk_score, 2),
        "method": "ml_ensemble",
        "features": features,
        "model_predictions": {
            "random_forest": round(rf_pred, 2),
            "xgboost": round(xgb_pred, 2),
            "lightgbm": round(lgb_pred, 2)
        }
    }

def detect_anomalies(earthquakes, target_lat, target_lon):
    """
    Anomali tespiti ile olağandışı deprem aktivitesi tespit eder.
    """
    features = extract_features(earthquakes, target_lat, target_lon)
    
    if features is None:
        return {"anomaly_detected": False, "anomaly_score": 0.0}
    
    # Anomali skorları
    anomaly_scores = []
    
    # 1. Aktivite yoğunluğu anomalisi
    if features.get('count', 0) > 20:
        anomaly_scores.append(0.3)
    
    # 2. Büyüklük anomalisi
    if features.get('max_magnitude', 0) >= 5.0:
        anomaly_scores.append(0.4)
    
    # 3. Mesafe anomalisi (çok yakın depremler)
    if features.get('min_distance', 300) < 20:
        anomaly_scores.append(0.5)
    
    # 4. Zaman aralığı anomalisi (çok sık depremler)
    if features.get('min_interval', 3600) < 300:  # 5 dakikadan az
        anomaly_scores.append(0.3)
    
    # 5. Büyüklük trendi anomalisi
    if features.get('magnitude_trend', 0) > 0.5:
        anomaly_scores.append(0.4)
    
    # 6. Isolation Forest ile anomali tespiti
    try:
        if os.path.exists(ANOMALY_DETECTION_MODEL_FILE):
            with open(ANOMALY_DETECTION_MODEL_FILE, 'rb') as f:
                isolation_model = pickle.load(f)
            
            feature_vector = np.array([[
                features.get('count', 0),
                features.get('max_magnitude', 0),
                features.get('mean_magnitude', 0),
                features.get('min_distance', 300),
                features.get('activity_density', 0)
            ]])
            
            anomaly_pred = isolation_model.predict(feature_vector)[0]
            if anomaly_pred == -1:  # Anomali
                anomaly_scores.append(0.6)
    except:
        pass
    
    total_anomaly_score = min(1.0, sum(anomaly_scores))
    anomaly_detected = total_anomaly_score > 0.5
    
    return {
        "anomaly_detected": anomaly_detected,
        "anomaly_score": round(total_anomaly_score, 2),
        "anomaly_factors": {
            "high_activity": features.get('count', 0) > 20,
            "high_magnitude": features.get('max_magnitude', 0) >= 5.0,
            "very_close": features.get('min_distance', 300) < 20,
            "frequent": features.get('min_interval', 3600) < 300,
            "increasing_trend": features.get('magnitude_trend', 0) > 0.5
        }
    }

def istanbul_early_warning_system(earthquakes):
    """
    İstanbul için özel erken uyarı sistemi.
    Deprem öncesi sinyalleri tespit eder.
    """
    istanbul_lat = ISTANBUL_COORDS['lat']
    istanbul_lon = ISTANBUL_COORDS['lon']
    
    # İstanbul çevresindeki depremleri filtrele
    istanbul_earthquakes = []
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            distance = haversine(istanbul_lat, istanbul_lon, lat, lon)
            
            if distance <= ISTANBUL_RADIUS:
                istanbul_earthquakes.append({
                    'mag': eq.get('mag', 0),
                    'distance': distance,
                    'depth': eq.get('depth', 10),
                    'lat': lat,
                    'lon': lon,
                    'timestamp': eq.get('timestamp', time.time()),
                    'location': eq.get('location', '')
                })
    
    if len(istanbul_earthquakes) == 0:
        return {
            "alert_level": "Normal",
            "alert_score": 0.0,
            "message": "İstanbul çevresinde anormal aktivite yok.",
            "time_to_event": None
        }
    
    # Özellik çıkarımı
    features = extract_features(earthquakes, istanbul_lat, istanbul_lon, time_window_hours=48)
    
    if features is None:
        return {
            "alert_level": "Normal",
            "alert_score": 0.0,
            "message": "Yeterli veri yok.",
            "time_to_event": None
        }
    
    # Erken uyarı skorları
    warning_scores = []
    warning_messages = []
    
    # 1. Aktivite artışı (son 48 saatte)
    recent_count = features.get('count', 0)
    if recent_count > 15:
        warning_scores.append(0.3)
        warning_messages.append(f"Son 48 saatte {recent_count} deprem tespit edildi (yüksek aktivite)")
    
    # 2. Büyüklük artışı
    max_mag = features.get('max_magnitude', 0)
    if max_mag >= 4.5:
        warning_scores.append(0.4)
        warning_messages.append(f"M{max_mag:.1f} büyüklüğünde deprem tespit edildi")
    
    # 3. Yakın mesafe
    min_dist = features.get('min_distance', 300)
    if min_dist < 50:
        warning_scores.append(0.5)
        warning_messages.append(f"Deprem merkezi İstanbul'a {min_dist:.1f} km uzaklıkta")
    
    # 4. Büyüklük trendi (artıyor mu?)
    mag_trend = features.get('magnitude_trend', 0)
    if mag_trend > 0.3:
        warning_scores.append(0.4)
        warning_messages.append("Deprem büyüklükleri artış eğiliminde")
    
    # 5. Sık depremler
    min_interval = features.get('min_interval', 3600)
    if min_interval < 600:  # 10 dakikadan az
        warning_scores.append(0.3)
        warning_messages.append("Çok sık deprem aktivitesi tespit edildi")
    
    # 6. Anomali tespiti
    anomaly_result = detect_anomalies(earthquakes, istanbul_lat, istanbul_lon)
    if anomaly_result['anomaly_detected']:
        warning_scores.append(0.5)
        warning_messages.append("Olağandışı deprem aktivitesi tespit edildi")
    
    # Toplam uyarı skoru
    total_score = min(1.0, sum(warning_scores))
    
    # Uyarı seviyesi
    if total_score >= 0.7:
        alert_level = "KRİTİK"
        time_to_event = "0-24 saat"
    elif total_score >= 0.5:
        alert_level = "YÜKSEK"
        time_to_event = "24-72 saat"
    elif total_score >= 0.3:
        alert_level = "ORTA"
        time_to_event = "72-168 saat (1 hafta)"
    else:
        alert_level = "DÜŞÜK"
        time_to_event = None
    
    # Tarihsel veri ile karşılaştırma
    ISTANBUL_ALERT_HISTORY.append({
        'timestamp': time.time(),
        'score': total_score,
        'features': features
    })
    
    return {
        "alert_level": alert_level,
        "alert_score": round(total_score, 2),
        "message": " | ".join(warning_messages) if warning_messages else "Normal aktivite",
        "time_to_event": time_to_event,
        "features": features,
        "recent_earthquakes": len(istanbul_earthquakes),
        "anomaly_detected": anomaly_result['anomaly_detected']
    }

def find_nearest_city(lat, lon):
    """ Verilen koordinatlara en yakın ili bulur. """
    min_distance = float('inf')
    nearest_city = None
    
    for city_name, city_data in TURKEY_CITIES.items():
        city_lat = city_data['lat']
        city_lon = city_data['lon']
        distance = haversine(lat, lon, city_lat, city_lon)
        
        if distance < min_distance:
            min_distance = distance
            nearest_city = city_name
    
    return nearest_city, min_distance

def turkey_early_warning_system(earthquakes, target_city=None):
    """
    Tüm Türkiye için erken uyarı sistemi.
    M ≥ 5.0 olabilecek yıkıcı depremlerden önce bildirim gönderir.
    target_city: Belirli bir il için analiz yapılacaksa (None ise tüm iller)
    """
    warnings = {}
    
    # Analiz edilecek şehirler
    cities_to_analyze = [target_city] if target_city and target_city in TURKEY_CITIES else list(TURKEY_CITIES.keys())
    
    for city_name in cities_to_analyze:
        city_data = TURKEY_CITIES[city_name]
        city_lat = city_data['lat']
        city_lon = city_data['lon']
        
        # Şehir çevresindeki depremleri filtrele (200 km yarıçap)
        city_earthquakes = []
        for eq in earthquakes:
            if eq.get('geojson') and eq['geojson'].get('coordinates'):
                lon, lat = eq['geojson']['coordinates']
                distance = haversine(city_lat, city_lon, lat, lon)
                
                if distance <= 200:
                    city_earthquakes.append({
                        'mag': eq.get('mag', 0),
                        'distance': distance,
                        'depth': eq.get('depth', 10),
                        'lat': lat,
                        'lon': lon,
                        'timestamp': eq.get('timestamp', time.time()),
                        'location': eq.get('location', '')
                    })
        
        if len(city_earthquakes) == 0:
            warnings[city_name] = {
                "alert_level": "Normal",
                "alert_score": 0.0,
                "message": f"{city_name} çevresinde anormal aktivite yok.",
                "time_to_event": None,
                "predicted_magnitude": None
            }
            continue
        
        # Özellik çıkarımı (son 7 gün)
        features = extract_features(earthquakes, city_lat, city_lon, time_window_hours=168)
        
        if features is None:
            warnings[city_name] = {
                "alert_level": "Normal",
                "alert_score": 0.0,
                "message": "Yeterli veri yok.",
                "time_to_event": None,
                "predicted_magnitude": None
            }
            continue
        
        # Erken uyarı skorları (M ≥ 5.0 deprem tahmini için)
        warning_scores = []
        warning_messages = []
        predicted_magnitude = 0.0
        
        # 1. Aktivite artışı (son 7 günde)
        recent_count = features.get('count', 0)
        if recent_count > 20:
            warning_scores.append(0.3)
            warning_messages.append(f"Son 7 günde {recent_count} deprem tespit edildi (yüksek aktivite)")
        
        # 2. Büyüklük artışı ve tahmin
        max_mag = features.get('max_magnitude', 0)
        mean_mag = features.get('mean_magnitude', 0)
        
        # Büyüklük trendi analizi
        mag_trend = features.get('magnitude_trend', 0)
        if mag_trend > 0.2:
            # Büyüklük artıyor, M ≥ 5.0 riski var
            predicted_magnitude = min(7.0, max_mag + mag_trend * 2)  # Tahmin
            if predicted_magnitude >= 5.0:
                warning_scores.append(0.5)
                warning_messages.append(f"M{predicted_magnitude:.1f} büyüklüğünde deprem riski tespit edildi")
        
        if max_mag >= 4.5:
            warning_scores.append(0.4)
            warning_messages.append(f"M{max_mag:.1f} büyüklüğünde deprem tespit edildi")
            if predicted_magnitude < max_mag:
                predicted_magnitude = max_mag
        
        # 3. Yakın mesafe (çok yakın depremler daha riskli)
        min_dist = features.get('min_distance', 300)
        if min_dist < 30:
            warning_scores.append(0.6)
            warning_messages.append(f"Deprem merkezi {city_name}'a {min_dist:.1f} km uzaklıkta (çok yakın)")
        elif min_dist < 50:
            warning_scores.append(0.4)
            warning_messages.append(f"Deprem merkezi {city_name}'a {min_dist:.1f} km uzaklıkta")
        
        # 4. Büyüklük trendi (artıyor mu?)
        if mag_trend > 0.3:
            warning_scores.append(0.5)
            warning_messages.append("Deprem büyüklükleri hızla artış eğiliminde")
        
        # 5. Sık depremler (swarm aktivitesi)
        min_interval = features.get('min_interval', 3600)
        if min_interval < 300:  # 5 dakikadan az
            warning_scores.append(0.4)
            warning_messages.append("Çok sık deprem aktivitesi (swarm) tespit edildi")
        
        # 6. Anomali tespiti
        anomaly_result = detect_anomalies(earthquakes, city_lat, city_lon)
        if anomaly_result['anomaly_detected']:
            warning_scores.append(0.6)
            warning_messages.append("Olağandışı deprem aktivitesi tespit edildi")
            if predicted_magnitude < 5.0:
                predicted_magnitude = 5.0  # Anomali varsa M ≥ 5.0 riski
        
        # 7. Fay hattı yakınlığı
        nearest_fault = features.get('nearest_fault_distance', 200)
        if nearest_fault < 25:
            warning_scores.append(0.3)
            warning_messages.append(f"Aktif fay hattına {nearest_fault:.1f} km uzaklıkta")
        
        # Toplam uyarı skoru
        total_score = min(1.0, sum(warning_scores))
        
        # Uyarı seviyesi ve tahmini süre (M ≥ 5.0 deprem için)
        if total_score >= 0.7 and predicted_magnitude >= 5.0:
            alert_level = "KRİTİK"
            time_to_event = "0-24 saat içinde"
        elif total_score >= 0.5 and predicted_magnitude >= 5.0:
            alert_level = "YÜKSEK"
            time_to_event = "24-72 saat içinde"
        elif total_score >= 0.4 and predicted_magnitude >= 4.5:
            alert_level = "ORTA"
            time_to_event = "72-168 saat içinde (1 hafta)"
        elif total_score >= 0.3:
            alert_level = "DÜŞÜK"
            time_to_event = "1-2 hafta içinde"
        else:
            alert_level = "Normal"
            time_to_event = None
        
        warnings[city_name] = {
            "alert_level": alert_level,
            "alert_score": round(total_score, 2),
            "message": " | ".join(warning_messages) if warning_messages else "Normal aktivite",
            "time_to_event": time_to_event,
            "predicted_magnitude": round(predicted_magnitude, 1) if predicted_magnitude > 0 else None,
            "features": features,
            "recent_earthquakes": len(city_earthquakes),
            "anomaly_detected": anomaly_result['anomaly_detected']
        }
    
    return warnings

def ai_damage_estimate(magnitude, depth, distance, building_structure):
    """
    Yapay zeka destekli hasar tahmini yapar.
    Bina yapısı dağılımını (güçlendirilmiş, normal, zayıf yüzdesi) kullanarak
    daha gerçekçi hasar tahmini yapar.
    """
    # Temel hasar skoru
    base_damage = magnitude * 2.5
    
    # Derinlik faktörü (daha derin depremler daha az hasar verir)
    depth_factor = max(0.4, 1 - (depth / 60))
    
    # Mesafe faktörü (uzaklık arttıkça hasar azalır - logaritmik)
    distance_factor = max(0.05, 1 / (1 + np.log1p(distance / 30)))
    
    # Bina yapısına göre ağırlıklı ortalama hasar faktörü
    reinforced_factor = 0.6  # Güçlendirilmiş binalar
    normal_factor = 1.0      # Normal binalar
    weak_factor = 1.8        # Zayıf binalar
    
    weighted_building_factor = (
        building_structure.get('reinforced', 0.25) * reinforced_factor +
        building_structure.get('normal', 0.50) * normal_factor +
        building_structure.get('weak', 0.25) * weak_factor
    )
    
    # Toplam hasar skoru (0-100 arası)
    damage_score = min(100, base_damage * depth_factor * distance_factor * weighted_building_factor)
    
    # Yapay zeka ile seviye belirleme (daha hassas eşikler)
    if damage_score >= 75:
        level = "Çok Yüksek"
        description = "Ağır hasar beklenir. Binalarda yıkılma riski çok yüksek. Acil tahliye gerekebilir."
        affected_buildings = {
            "reinforced": round(building_structure.get('reinforced', 0.25) * 0.15 * 100, 1),
            "normal": round(building_structure.get('normal', 0.50) * 0.40 * 100, 1),
            "weak": round(building_structure.get('weak', 0.25) * 0.80 * 100, 1)
        }
    elif damage_score >= 55:
        level = "Yüksek"
        description = "Önemli hasar beklenir. Binalarda ciddi çatlaklar ve yapısal hasarlar olabilir."
        affected_buildings = {
            "reinforced": round(building_structure.get('reinforced', 0.25) * 0.08 * 100, 1),
            "normal": round(building_structure.get('normal', 0.50) * 0.25 * 100, 1),
            "weak": round(building_structure.get('weak', 0.25) * 0.60 * 100, 1)
        }
    elif damage_score >= 35:
        level = "Orta"
        description = "Orta seviye hasar beklenir. Duvar çatlakları ve küçük yapısal hasarlar olabilir."
        affected_buildings = {
            "reinforced": round(building_structure.get('reinforced', 0.25) * 0.03 * 100, 1),
            "normal": round(building_structure.get('normal', 0.50) * 0.15 * 100, 1),
            "weak": round(building_structure.get('weak', 0.25) * 0.35 * 100, 1)
        }
    elif damage_score >= 18:
        level = "Düşük"
        description = "Hafif hasar beklenir. Cam kırılmaları ve küçük çatlaklar olabilir."
        affected_buildings = {
            "reinforced": round(building_structure.get('reinforced', 0.25) * 0.01 * 100, 1),
            "normal": round(building_structure.get('normal', 0.50) * 0.08 * 100, 1),
            "weak": round(building_structure.get('weak', 0.25) * 0.20 * 100, 1)
        }
    else:
        level = "Minimal"
        description = "Minimal hasar beklenir. Sadece eşya devrilmeleri olabilir."
        affected_buildings = {
            "reinforced": 0,
            "normal": round(building_structure.get('normal', 0.50) * 0.03 * 100, 1),
            "weak": round(building_structure.get('weak', 0.25) * 0.10 * 100, 1)
        }
    
    return {
        "damage_score": round(damage_score, 1),
        "level": level,
        "description": description,
        "affected_buildings_percent": affected_buildings,
        "factors": {
            "magnitude_impact": round(base_damage, 1),
            "depth_factor": round(depth_factor, 2),
            "distance_factor": round(distance_factor, 2),
            "weighted_building_factor": round(weighted_building_factor, 2)
        }
    }

def calculate_damage_estimate(magnitude, depth, distance, building_type="normal"):
    """
    Deprem hasar tahmini yapar.
    magnitude: Deprem büyüklüğü (Richter)
    depth: Deprem derinliği (km)
    distance: Mesafe (km)
    building_type: Bina tipi ("normal", "reinforced", "weak")
    """
    # Temel hasar skoru hesaplama
    base_damage = magnitude * 2
    
    # Derinlik faktörü (daha derin depremler daha az hasar verir)
    depth_factor = max(0.5, 1 - (depth / 50))
    
    # Mesafe faktörü (uzaklık arttıkça hasar azalır)
    distance_factor = max(0.1, 1 / (1 + distance / 50))
    
    # Bina tipi faktörü
    building_factors = {
        "normal": 1.0,
        "reinforced": 0.6,  # Güçlendirilmiş binalar
        "weak": 1.5  # Zayıf binalar
    }
    building_factor = building_factors.get(building_type, 1.0)
    
    # Toplam hasar skoru (0-100 arası)
    damage_score = min(100, base_damage * depth_factor * distance_factor * building_factor)
    
    # Hasar seviyesi belirleme
    if damage_score >= 70:
        level = "Çok Yüksek"
        description = "Ağır hasar beklenir. Binalarda yıkılma riski yüksek."
    elif damage_score >= 50:
        level = "Yüksek"
        description = "Önemli hasar beklenir. Binalarda çatlaklar ve yapısal hasarlar olabilir."
    elif damage_score >= 30:
        level = "Orta"
        description = "Orta seviye hasar beklenir. Duvar çatlakları ve küçük yapısal hasarlar olabilir."
    elif damage_score >= 15:
        level = "Düşük"
        description = "Hafif hasar beklenir. Cam kırılmaları ve küçük çatlaklar olabilir."
    else:
        level = "Minimal"
        description = "Minimal hasar beklenir. Sadece eşya devrilmeleri olabilir."
    
    return {
        "damage_score": round(damage_score, 1),
        "level": level,
        "description": description,
        "factors": {
            "magnitude_impact": round(base_damage, 1),
            "depth_factor": round(depth_factor, 2),
            "distance_factor": round(distance_factor, 2),
            "building_factor": building_factor
        }
    }

def predict_earthquake_risk(earthquakes, target_lat, target_lon):
    """
    Yapay zeka destekli deprem risk tahmini yapar.
    Son depremlerin pattern'ini analiz ederek risk skoru hesaplar.
    İYİLEŞTİRİLMİŞ VERSİYON: Daha sağlıklı ve dengeli risk skorlama.
    """
    # Yakın fay hattı kontrolü (her zaman hesaplanır)
    nearest_fault_distance = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            fault_lat, fault_lon = coord
            dist = haversine(target_lat, target_lon, fault_lat, fault_lon)
            nearest_fault_distance = min(nearest_fault_distance, dist)
    
    # Deprem verisi yoksa bile fay hattı mesafesine göre temel risk döndür
    if not earthquakes or len(earthquakes) == 0:
        # Sadece fay hattı mesafesine göre risk
        if nearest_fault_distance < 20:
            base_risk = 3.5
        elif nearest_fault_distance < 50:
            base_risk = 2.5
        elif nearest_fault_distance < 100:
            base_risk = 1.5
        else:
            base_risk = 1.0
        
        level = "Düşük" if base_risk < 2.5 else "Orta"
        return {
            "risk_level": level,
            "risk_score": round(base_risk, 1),
            "factors": {
                "max_magnitude": 0,
                "recent_count": 0,
                "avg_distance": 0,
                "nearest_fault_km": round(nearest_fault_distance, 1)
            },
            "reason": f"Yakın bölgede son deprem aktivitesi yok. En yakın fay hattı: {nearest_fault_distance:.1f} km"
        }
    
    # Son 7 gün içindeki depremleri filtrele (24 saat yerine 7 gün - daha kapsamlı analiz)
    recent_earthquakes = []
    current_time = time.time()
    seven_days_ago = current_time - (7 * 24 * 3600)
    
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            mag = eq.get('mag', 0)
            timestamp = eq.get('timestamp', 0)
            distance = haversine(target_lat, target_lon, lat, lon)
            
            # 300 km içindeki tüm depremleri al (magnitude filtresi yok - tüm depremler önemli)
            if distance < 300 and timestamp >= seven_days_ago:
                recent_earthquakes.append({
                    'mag': mag,
                    'distance': distance,
                    'lat': lat,
                    'lon': lon,
                    'depth': eq.get('depth', 10),
                    'timestamp': timestamp
                })
    
    # Risk faktörleri hesaplama
    if not recent_earthquakes:
        # Deprem yok ama fay hattı yakınsa risk var
        if nearest_fault_distance < 20:
            base_risk = 3.0
        elif nearest_fault_distance < 50:
            base_risk = 2.0
        elif nearest_fault_distance < 100:
            base_risk = 1.5
        else:
            base_risk = 1.0
        
        level = "Düşük" if base_risk < 2.5 else "Orta"
        return {
            "risk_level": level,
            "risk_score": round(base_risk, 1),
            "factors": {
                "max_magnitude": 0,
                "recent_count": 0,
                "avg_distance": 0,
                "nearest_fault_km": round(nearest_fault_distance, 1)
            },
            "reason": f"Son 7 günde yakın bölgede aktivite yok. En yakın fay hattı: {nearest_fault_distance:.1f} km"
        }
    
    # İstatistikler
    magnitudes = [eq['mag'] for eq in recent_earthquakes]
    distances = [eq['distance'] for eq in recent_earthquakes]
    depths = [eq['depth'] for eq in recent_earthquakes]
    
    avg_magnitude = np.mean(magnitudes)
    max_magnitude = max(magnitudes)
    count = len(recent_earthquakes)
    avg_distance = np.mean(distances)
    min_distance = min(distances)
    avg_depth = np.mean(depths)
    
    # İyileştirilmiş Risk Skoru Hesaplama (0-10 arası, daha dengeli)
    risk_score = 0.0
    
    # 1. Büyüklük faktörü (0-3.5 puan) - Daha dengeli
    if max_magnitude >= 6.0:
        risk_score += 3.5
    elif max_magnitude >= 5.0:
        risk_score += 2.5
    elif max_magnitude >= 4.5:
        risk_score += 1.8
    elif max_magnitude >= 4.0:
        risk_score += 1.2
    else:
        risk_score += max_magnitude * 0.3
    
    # 2. Aktivite yoğunluğu (0-2.5 puan) - Logaritmik artış
    if count >= 50:
        risk_score += 2.5
    elif count >= 20:
        risk_score += 2.0
    elif count >= 10:
        risk_score += 1.5
    elif count >= 5:
        risk_score += 1.0
    else:
        risk_score += count * 0.15
    
    # 3. Mesafe faktörü (0-2.0 puan) - Yakın depremler çok riskli
    if min_distance < 10:
        risk_score += 2.0
    elif min_distance < 25:
        risk_score += 1.5
    elif min_distance < 50:
        risk_score += 1.0
    elif min_distance < 100:
        risk_score += 0.5
    elif avg_distance < 150:
        risk_score += 0.3
    
    # 4. Fay hattı yakınlığı (0-1.5 puan)
    if nearest_fault_distance < 10:
        risk_score += 1.5
    elif nearest_fault_distance < 25:
        risk_score += 1.2
    elif nearest_fault_distance < 50:
        risk_score += 0.8
    elif nearest_fault_distance < 100:
        risk_score += 0.4
    
    # 5. Derinlik faktörü (0-0.5 puan) - Sığ depremler daha riskli
    if avg_depth < 5:
        risk_score += 0.5
    elif avg_depth < 10:
        risk_score += 0.3
    
    # 6. Büyük deprem sayısı (0-0.5 puan)
    large_quakes = sum(1 for m in magnitudes if m >= 4.5)
    if large_quakes >= 3:
        risk_score += 0.5
    elif large_quakes >= 1:
        risk_score += 0.3
    
    # Skoru 0-10 arasına sınırla
    risk_score = min(10.0, max(0.0, risk_score))
    
    # Risk seviyesi belirleme (daha hassas eşikler)
    if risk_score >= 7.5:
        level = "Çok Yüksek"
    elif risk_score >= 6.0:
        level = "Yüksek"
    elif risk_score >= 4.0:
        level = "Orta-Yüksek"
    elif risk_score >= 2.5:
        level = "Orta"
    elif risk_score >= 1.5:
        level = "Düşük-Orta"
    else:
        level = "Düşük"
    
    return {
        "risk_level": level,
        "risk_score": round(risk_score, 1),
        "factors": {
            "max_magnitude": round(max_magnitude, 1),
            "avg_magnitude": round(avg_magnitude, 1),
            "recent_count": count,
            "min_distance": round(min_distance, 1),
            "avg_distance": round(avg_distance, 1),
            "nearest_fault_km": round(nearest_fault_distance, 1),
            "avg_depth": round(avg_depth, 1)
        },
        "reason": f"Son 7 günde {count} deprem, en büyük M{max_magnitude:.1f}, en yakın {min_distance:.1f} km"
    }


# --- API UÇ NOKTALARI ---

@app.route('/api/risk', methods=['GET'])
def get_risk_analysis():
    """ Ön uçtan gelen isteklere YZ analiz sonuçlarını döndürür. """
    
    print("Risk analizi isteği alındı...")
    start_time = time.time()
    
    try:
        # Deprem verilerini çek
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                earthquake_data = []  # Boş liste ile devam et
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            earthquake_data = []  # Boş liste ile devam et
        
        # Risk analizi yap
        try:
            risk_data = calculate_clustering_risk(earthquake_data)
            risk_data['fault_lines'] = TURKEY_FAULT_LINES
            risk_data['recent_earthquakes'] = earthquake_data[:20] if earthquake_data else []  # Son 20 deprem
            
            end_time = time.time()
            print(f"Analiz süresi: {end_time - start_time:.2f} saniye")
            
            return jsonify(risk_data)
        except Exception as e:
            print(f"[ERROR] Risk analizi hesaplama hatası: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: Sadece fault lines döndür
            return jsonify({
                "status": "error",
                "risk_regions": [],
                "fault_lines": TURKEY_FAULT_LINES,
                "recent_earthquakes": earthquake_data[:20] if earthquake_data else [],
                "message": f"Risk analizi yapılamadı: {str(e)}"
            })
            
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "risk_regions": [],
            "fault_lines": TURKEY_FAULT_LINES,
            "recent_earthquakes": [],
            "message": f"Sunucu hatası: {str(e)}"
        }), 500

@app.route('/api/damage-estimate', methods=['POST'])
def estimate_damage():
    """ Deprem hasar tahmini yapar. """
    data = request.get_json()
    magnitude = float(data.get('magnitude', 0))
    depth = float(data.get('depth', 10))
    distance = float(data.get('distance', 0))
    building_type = data.get('building_type', 'normal')
    
    if magnitude <= 0:
        return jsonify({"error": "Geçerli bir büyüklük değeri giriniz."}), 400
    
    damage_estimate = calculate_damage_estimate(magnitude, depth, distance, building_type)
    return jsonify(damage_estimate)

@app.route('/api/predict-risk', methods=['POST'])
def predict_risk():
    """ Belirli bir konum için gelişmiş ML destekli deprem risk tahmini yapar. """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Geçersiz istek. JSON verisi bekleniyor."}), 400
        
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        
        # Koordinat kontrolü
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Geçersiz koordinatlar. Enlem: -90 ile 90, Boylam: -180 ile 180 arasında olmalı."}), 400
        
        use_ml = data.get('use_ml', True)  # ML kullanımı (varsayılan: True)
        
        # Deprem verilerini çek
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                # Veri yoksa bile temel risk analizi yap (fay hattı mesafesi vb.)
                earthquake_data = []
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            earthquake_data = []  # Boş liste ile devam et
        
        # Gelişmiş ML modeli ile tahmin
        try:
            if use_ml:
                prediction = predict_risk_with_ml(earthquake_data, lat, lon)
                # Anomali tespiti ekle
                try:
                    anomaly = detect_anomalies(earthquake_data, lat, lon)
                    prediction['anomaly'] = anomaly
                except Exception as e:
                    print(f"[WARNING] Anomali tespiti başarısız: {e}")
                    prediction['anomaly'] = {"anomaly_detected": False, "anomaly_score": 0.0}
            else:
                # Eski yöntem (fallback)
                prediction = predict_earthquake_risk(earthquake_data, lat, lon)
                prediction['method'] = 'traditional'
            
            # Method kontrolü
            if 'method' not in prediction:
                prediction['method'] = 'ml_ensemble' if use_ml else 'traditional'
            
            return jsonify(prediction)
            
        except Exception as e:
            print(f"[ERROR] Risk tahmini hatası: {e}")
            # Son çare: Basit risk analizi
            try:
                prediction = predict_earthquake_risk(earthquake_data, lat, lon)
                prediction['method'] = 'fallback'
                prediction['warning'] = 'Gelişmiş analiz başarısız, temel analiz kullanıldı'
                return jsonify(prediction)
            except Exception as e2:
                print(f"[ERROR] Fallback risk tahmini de başarısız: {e2}")
                return jsonify({
                    "error": "Risk analizi yapılamadı",
                    "risk_level": "Bilinmiyor",
                    "risk_score": 0,
                    "method": "error",
                    "message": str(e2)
                }), 500
                
    except ValueError as e:
        return jsonify({"error": f"Geçersiz veri formatı: {str(e)}"}), 400
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 500

@app.route('/api/istanbul-early-warning', methods=['GET'])
def istanbul_early_warning():
    """ İstanbul için özel erken uyarı sistemi. """
    try:
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                return jsonify({
                    "alert_level": "BİLGİ YOK",
                    "alert_score": 0.0,
                    "message": "API'den veri alınamadı.",
                    "recent_earthquakes": 0,
                    "anomaly_detected": False
                })
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            return jsonify({
                "alert_level": "BİLGİ YOK",
                "alert_score": 0.0,
                "message": f"Veri kaynağına erişilemedi: {str(e)}",
                "recent_earthquakes": 0,
                "anomaly_detected": False
            })
        
        try:
            warning = istanbul_early_warning_system(earthquake_data)
            return jsonify(warning)
        except Exception as e:
            print(f"[ERROR] İstanbul erken uyarı sistemi hatası: {e}")
            return jsonify({
                "alert_level": "HATA",
                "alert_score": 0.0,
                "message": f"Erken uyarı sistemi hatası: {str(e)}",
                "recent_earthquakes": 0,
                "anomaly_detected": False
            }), 500
            
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return jsonify({
            "alert_level": "HATA",
            "alert_score": 0.0,
            "message": f"Sunucu hatası: {str(e)}",
            "recent_earthquakes": 0,
            "anomaly_detected": False
        }), 500

@app.route('/api/train-models', methods=['POST'])
def train_models():
    """ ML modellerini eğitir (tarihsel veri ile). """
    try:
        # Tarihsel veriyi yükle
        if os.path.exists(EARTHQUAKE_HISTORY_FILE):
            with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            return jsonify({"error": "Tarihsel veri bulunamadı. Önce veri toplama yapılmalı."}), 400
        
        # Model eğit
        models = train_risk_prediction_model(history)
        
        if models:
            return jsonify({
                "status": "success",
                "message": "Modeller başarıyla eğitildi.",
                "models_trained": list(models.keys())
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Model eğitilemedi. Yeterli veri yok."
            }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anomaly-detection', methods=['POST'])
def anomaly_detection():
    """ Anomali tespiti yapar. """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Geçersiz istek. JSON verisi bekleniyor."}), 400
        
        try:
            lat = float(data.get('lat', 0))
            lon = float(data.get('lon', 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Geçersiz koordinat formatı."}), 400
        
        # Koordinat kontrolü
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Geçersiz koordinatlar."}), 400
        
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                return jsonify({
                    "anomaly_detected": False,
                    "anomaly_score": 0.0,
                    "message": "API'den veri alınamadı."
                })
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            return jsonify({
                "anomaly_detected": False,
                "anomaly_score": 0.0,
                "message": f"Veri kaynağına erişilemedi: {str(e)}"
            })
        
        try:
            anomaly = detect_anomalies(earthquake_data, lat, lon)
            return jsonify(anomaly)
        except Exception as e:
            print(f"[ERROR] Anomali tespiti hatası: {e}")
            return jsonify({
                "anomaly_detected": False,
                "anomaly_score": 0.0,
                "message": f"Anomali tespiti başarısız: {str(e)}"
            }), 500
            
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 500

@app.route('/api/fault-lines', methods=['GET'])
def get_fault_lines():
    """ Türkiye'nin aktif fay hatlarını döndürür. (Ayrıca Render.com uyanık tutma için kullanılır) """
    return jsonify({"fault_lines": TURKEY_FAULT_LINES, "status": "ok"})

@app.route('/api/health', methods=['GET'])
def health_check():
    """ Health check endpoint - Render.com uyanık tutma için """
    return jsonify({"status": "ok", "message": "Server is awake"}), 200

@app.route('/api/turkey-early-warning', methods=['GET'])
def turkey_early_warning():
    """ Tüm Türkiye için erken uyarı sistemi - M ≥ 5.0 deprem riski tahmini """
    try:
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                earthquake_data = []
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            earthquake_data = []
        
        try:
            warnings = turkey_early_warning_system(earthquake_data)
            
            # Sadece uyarı veren şehirleri filtrele
            active_warnings = {city: data for city, data in warnings.items() 
                             if data['alert_level'] in ['KRİTİK', 'YÜKSEK', 'ORTA']}
            
            return jsonify({
                "status": "success",
                "total_cities_analyzed": len(warnings),
                "cities_with_warnings": len(active_warnings),
                "warnings": warnings,
                "active_warnings": active_warnings
            })
        except Exception as e:
            print(f"[ERROR] Türkiye erken uyarı sistemi hatası: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "status": "error",
                "message": f"Erken uyarı sistemi hatası: {str(e)}",
                "warnings": {}
            }), 500
            
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return jsonify({
            "status": "error",
            "message": f"Sunucu hatası: {str(e)}",
            "warnings": {}
        }), 500

@app.route('/api/city-damage-analysis', methods=['GET'])
def city_damage_analysis():
    """ İl bazında risk tahmini: Son depremlere ve aktif fay hatlarına göre. """
    try:
        try:
            earthquake_data = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquake_data:
                earthquake_data = []  # Boş liste ile devam et
        except Exception as e:
            print(f"[WARNING] API'den veri çekilemedi: {e}")
            earthquake_data = []  # Boş liste ile devam et
    
        # Son 24 saatteki tüm depremleri kullan (magnitude filtresi yok)
        recent_earthquakes = []
        current_time = time.time()
        
        for eq in earthquake_data:
            if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
                continue
            # Son 24 saat içindeki depremler
            eq_time_str = f"{eq.get('date', '')} {eq.get('time', '')}"
            recent_earthquakes.append(eq)
        
        city_risks = {}
        
        # Her il için risk hesapla
        for city_name, city_data in TURKEY_CITIES.items():
            city_lat = city_data['lat']
            city_lon = city_data['lon']
            
            # 1. Son depremlere yakınlık analizi
            earthquake_risk_score = 0.0
            earthquake_count = 0
            nearest_earthquake_distance = float('inf')
            max_nearby_magnitude = 0.0
            affecting_earthquakes = []
            
            for eq in recent_earthquakes:
                lon_eq, lat_eq = eq['geojson']['coordinates']
                magnitude = eq.get('mag', 0)
                depth = eq.get('depth', 10)
                distance = haversine(lat_eq, lon_eq, city_lat, city_lon)
                
                # 200 km içindeki depremleri analiz et
                if distance <= 200:
                    earthquake_count += 1
                    nearest_earthquake_distance = min(nearest_earthquake_distance, distance)
                    max_nearby_magnitude = max(max_nearby_magnitude, magnitude)
                    
                    # Mesafe ve büyüklüğe göre risk skoru
                    distance_factor = max(0, (200 - distance) / 200)  # 0-1 arası
                    magnitude_factor = min(1.0, magnitude / 7.0)  # M7.0 = max
                    risk_contribution = distance_factor * magnitude_factor * 30  # Max 30 puan
                    earthquake_risk_score += risk_contribution
                    
                    affecting_earthquakes.append({
                        "magnitude": round(magnitude, 1),
                        "distance": round(distance, 1),
                        "depth": depth,
                        "location": eq.get('location', 'Bilinmiyor'),
                        "date": eq.get('date', ''),
                        "time": eq.get('time', '')
                    })
            
            # 2. Aktif fay hatlarına yakınlık analizi
            fault_risk_score = 0.0
            nearest_fault_distance = float('inf')
            nearest_fault_name = None
            
            for fault in TURKEY_FAULT_LINES:
                for coord in fault['coords']:
                    fault_lat, fault_lon = coord
                    dist = haversine(city_lat, city_lon, fault_lat, fault_lon)
                    nearest_fault_distance = min(nearest_fault_distance, dist)
                    if nearest_fault_distance == dist:
                        nearest_fault_name = fault['name']
            
            # Fay hattı yakınlığına göre risk (0-40 puan)
            if nearest_fault_distance < 20:
                fault_risk_score = 40  # Çok yakın
            elif nearest_fault_distance < 50:
                fault_risk_score = 30  # Yakın
            elif nearest_fault_distance < 100:
                fault_risk_score = 20  # Orta mesafe
            elif nearest_fault_distance < 150:
                fault_risk_score = 10  # Uzak
            else:
                fault_risk_score = 0  # Çok uzak
            
            # 3. Deprem aktivitesi yoğunluğu (0-30 puan)
            activity_score = min(30, earthquake_count * 2)  # Her deprem 2 puan, max 30
            
            # 4. Toplam risk skoru (0-100)
            total_risk_score = min(100, earthquake_risk_score + fault_risk_score + activity_score)
            
            # Risk seviyesi belirleme
            if total_risk_score >= 70:
                risk_level = "Çok Yüksek"
                risk_description = f"{city_name} için çok yüksek deprem riski tespit edildi. Yakın bölgede aktif deprem aktivitesi ve fay hatlarına yakınlık nedeniyle dikkatli olunmalı."
            elif total_risk_score >= 50:
                risk_level = "Yüksek"
                risk_description = f"{city_name} için yüksek deprem riski var. Son depremler ve fay hatlarına yakınlık nedeniyle hazırlıklı olunmalı."
            elif total_risk_score >= 30:
                risk_level = "Orta"
                risk_description = f"{city_name} için orta seviye deprem riski var. Son deprem aktivitesi ve fay hatlarına mesafe dikkate alınmalı."
            elif total_risk_score >= 15:
                risk_level = "Düşük"
                risk_description = f"{city_name} için düşük deprem riski. Genel deprem hazırlığı önerilir."
            else:
                risk_level = "Minimal"
                risk_description = f"{city_name} için minimal deprem riski. Genel güvenlik önlemleri yeterli."
            
            # Bina risk analizi - En yakın ve en büyük depreme göre
            building_risk_analysis = None
            if affecting_earthquakes:
                # En riskli depremi bul (büyüklük ve mesafeye göre)
                most_risky_eq = max(affecting_earthquakes, key=lambda x: x['magnitude'] / (x['distance'] + 1))
                
                # Bina yapısı bilgisi
                building_structure = city_data.get('building_structure', {"reinforced": 0.25, "normal": 0.50, "weak": 0.25})
                
                # Hasar tahmini yap
                damage_estimate = ai_damage_estimate(
                    magnitude=most_risky_eq['magnitude'],
                    depth=most_risky_eq.get('depth', 10),
                    distance=most_risky_eq['distance'],
                    building_structure=building_structure
                )
                
                building_risk_analysis = {
                    "damage_score": damage_estimate['damage_score'],
                    "damage_level": damage_estimate['level'],
                    "damage_description": damage_estimate['description'],
                    "affected_buildings_percent": damage_estimate['affected_buildings_percent'],
                    "building_structure": building_structure,
                    "based_on_earthquake": {
                        "magnitude": most_risky_eq['magnitude'],
                        "distance": most_risky_eq['distance'],
                        "location": most_risky_eq['location']
                    },
                    "factors": damage_estimate['factors']
                }
            
            city_risks[city_name] = {
                "city": city_name,
                "lat": city_lat,
                "lon": city_lon,
                "risk_score": round(total_risk_score, 1),
                "risk_level": risk_level,
                "description": risk_description,
                "factors": {
                    "earthquake_risk": round(earthquake_risk_score, 1),
                    "fault_risk": round(fault_risk_score, 1),
                    "activity_score": round(activity_score, 1),
                    "nearest_fault_distance": round(nearest_fault_distance, 1),
                    "nearest_fault_name": nearest_fault_name,
                    "earthquake_count": earthquake_count,
                    "max_nearby_magnitude": round(max_nearby_magnitude, 1),
                    "nearest_earthquake_distance": round(nearest_earthquake_distance, 1) if nearest_earthquake_distance != float('inf') else None
                },
                "affecting_earthquakes": affecting_earthquakes[:5],  # En yakın 5 deprem
                "building_structure": city_data.get('building_structure', {"reinforced": 0.25, "normal": 0.50, "weak": 0.25}),
                "building_risk_analysis": building_risk_analysis  # YENİ: Bina risk analizi
            }
        
        # Sıralama: En yüksek risk skoruna göre
        sorted_cities = sorted(
            city_risks.values(),
            key=lambda x: x['risk_score'],
            reverse=True
        )
        
        return jsonify({
            "status": "success",
            "total_earthquakes": len(recent_earthquakes),
            "analyzed_cities": len(sorted_cities),
            "city_risks": sorted_cities
        })
    except Exception as e:
        print(f"[ERROR] İl bazında risk analizi hatası: {e}")
        return jsonify({
            "status": "error",
            "message": f"Risk analizi yapılamadı: {str(e)}",
            "city_risks": []
        }), 500

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """ Gelişmiş deprem asistanı chatbot endpoint'i. """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Üzgünüm, mesajınızı anlayamadım. Lütfen tekrar deneyin."}), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({"response": "Lütfen bir mesaj yazın."}), 400
        
        message_lower = message.lower()
        
        # Gelişmiş rule-based AI - Çoklu anahtar kelime desteği
        responses = {
            # Selamlama
            ('merhaba', 'selam', 'hey', 'hi', 'hello'): 'Merhaba! 👋 Ben deprem asistanınız. Deprem güvenliği, risk analizi ve erken uyarı sistemi hakkında size yardımcı olabilirim. Nasıl yardımcı olabilirim?',
            
            # Risk analizi
            ('risk', 'risk analizi', 'risk tahmini', 'tehlike', 'güvenli mi'): '🔍 Risk analizi için:\n• Haritadaki "Risk Analizi" bölümünü kullanabilirsiniz\n• "Konumum İçin Risk Tahmini Yap" butonu ile kişisel analiz yapabilirsiniz\n• "İl Bazında Risk Analizi" ile tüm illerin risk durumunu görebilirsiniz\n\nSistem son depremlere ve aktif fay hatlarına göre analiz yapar.',
            
            # Deprem bilgileri
            ('deprem', 'depremler', 'son deprem', 'deprem listesi', 'deprem haritası'): '📊 Deprem bilgileri için:\n• "Son 1 Gün Depremler & Aktif Fay Hatları" haritasından son depremleri görebilirsiniz\n• Haritada deprem büyüklüğü, konum ve tarih bilgileri görüntülenir\n• İstanbul için özel erken uyarı sistemi mevcuttur',
            
            # Güvenlik
            ('güvenlik', 'güvenli', 'ne yapmalı', 'nasıl korunur', 'önlem', 'hazırlık', 'deprem sırasında', 'deprem öncesi', 'deprem sonrası'): '🛡️ DEPREM GÜVENLİĞİ:\n\n📌 DEPREM ÖNCESİ:\n• Acil durum çantası hazırlayın\n• Aile acil durum planı yapın\n• Güvenli yerleri belirleyin\n• Mobilyaları sabitleyin\n\n📌 DEPREM SIRASINDA:\n• ÇÖK: Yere çökün\n• KAPAN: Başınızı ve boynunuzu koruyun\n• TUTUN: Sağlam bir yere tutunun\n• Pencerelerden, dolaplardan uzak durun\n\n📌 DEPREM SONRASI:\n• Gaz, elektrik ve su vanalarını kapatın\n• Açık alanlara çıkın\n• Binalara girmeyin\n• Acil durum çantanızı alın',
            
            # İstanbul
            ('istanbul', 'istanbul uyarı', 'istanbul erken uyarı', 'istanbul risk'): '🏛️ İSTANBUL ERKEN UYARI SİSTEMİ:\n• İstanbul için özel gelişmiş yapay zeka destekli erken uyarı sistemi\n• "İstanbul Erken Uyarı Durumunu Kontrol Et" butonundan kontrol edebilirsiniz\n• Sistem deprem öncesi sinyalleri tespit ederek önceden uyarı verir\n• Uyarı seviyeleri: KRİTİK, YÜKSEK, ORTA, DÜŞÜK',
            
            # Fay hatları
            ('fay', 'fay hattı', 'fay hatları', 'kaf', 'daf', 'aktif fay'): '🗺️ TÜRKİYE AKTİF FAY HATLARI:\n• Kuzey Anadolu Fay Hattı (KAF)\n• Doğu Anadolu Fay Hattı (DAF)\n• Ege Graben Sistemi\n• Batı Anadolu Fay Sistemi\n\nHaritada "Son 1 Gün Depremler & Aktif Fay Hatları" bölümünden tüm fay hatlarını görebilirsiniz.',
            
            # Hasar tahmini
            ('hasar', 'hasar tahmini', 'hasar analizi', 'yıkım', 'zarar'): '🏙️ HASAR TAHMİNİ:\n• "İl Bazında Risk Analizi" bölümünden tüm illerin risk durumunu görebilirsiniz\n• Sistem son depremlere ve fay hatlarına yakınlığa göre analiz yapar\n• Her il için risk skoru, seviye ve detaylı faktörler gösterilir',
            
            # Bildirim
            ('bildirim', 'uyarı', 'whatsapp', 'mesaj', 'sms', 'alarm'): '📱 WHATSAPP BİLDİRİMLERİ:\n• "Acil Durum WhatsApp Bildirim Ayarları" bölümünden ayarlayabilirsiniz\n• Konumunuzu belirleyin\n• WhatsApp numaranızı girin (ülke kodu ile: +90...)\n• M ≥ 5.0 depremlerde 150 km içindeyse otomatik bildirim alırsınız',
            
            # Yardım
            ('yardım', 'help', 'nasıl kullanılır', 'kullanım', 'ne yapabilirsin'): '💡 NASIL KULLANILIR:\n\n1️⃣ Risk Analizi: Konumunuzu belirleyip risk tahmini yapın\n2️⃣ Deprem Haritası: Son depremleri ve fay hatlarını görüntüleyin\n3️⃣ İl Bazında Analiz: Tüm illerin risk durumunu kontrol edin\n4️⃣ İstanbul Uyarı: İstanbul için erken uyarı durumunu kontrol edin\n5️⃣ Bildirimler: WhatsApp bildirimlerini aktifleştirin\n\nBaşka bir sorunuz varsa sorabilirsiniz!',
            
            # Sistem bilgisi
            ('nasıl çalışır', 'sistem', 'yapay zeka', 'ml', 'makine öğrenmesi', 'algoritma'): '🤖 SİSTEM NASIL ÇALIŞIR:\n• Kandilli Rasathanesi verilerini kullanır\n• Gerçek zamanlı deprem analizi yapar\n• Makine öğrenmesi modelleri (Random Forest, XGBoost, LightGBM) ile risk tahmini\n• Anomali tespiti ile olağandışı aktivite tespit eder\n• Aktif fay hatlarına yakınlık analizi\n• Ensemble model ile yüksek doğruluk',
            
            # Teşekkür
            ('teşekkür', 'teşekkürler', 'sağol', 'sağolun', 'thanks', 'thank you'): 'Rica ederim! 😊 Başka bir sorunuz varsa çekinmeyin. Deprem güvenliğiniz için her zaman buradayım!',
            
            # Genel bilgi
            ('kandilli', 'veri', 'kaynak', 'nereden'): '📡 VERİ KAYNAĞI:\n• Kandilli Rasathanesi ve Deprem Araştırma Enstitüsü\n• Gerçek zamanlı deprem verileri\n• API: api.orhanaydogdu.com.tr\n• Veriler sürekli güncellenir',
        }
        
        # Çoklu anahtar kelime eşleştirme
        response_text = None
        matched_keywords = []
        
        for keywords, response in responses.items():
            for keyword in keywords:
                if keyword in message_lower:
                    response_text = response
                    matched_keywords.append(keyword)
                    break
            if response_text:
                break
        
        # Eğer eşleşme yoksa, benzer kelimeleri kontrol et
        if not response_text:
            # Kısmi eşleşme
            similar_patterns = {
                'risk': responses[('risk', 'risk analizi', 'risk tahmini', 'tehlike', 'güvenli mi')],
                'deprem': responses[('deprem', 'depremler', 'son deprem', 'deprem listesi', 'deprem haritası')],
                'güven': responses[('güvenlik', 'güvenli', 'ne yapmalı', 'nasıl korunur', 'önlem', 'hazırlık', 'deprem sırasında', 'deprem öncesi', 'deprem sonrası')],
            }
            
            for pattern, response in similar_patterns.items():
                if pattern in message_lower:
                    response_text = response
                    break
        
        # Son çare: Genel yanıt
        if not response_text:
            response_text = '🤔 Anladım, ancak bu konuda daha fazla bilgi veremiyorum. Size şunlar hakkında yardımcı olabilirim:\n\n• 🔍 Risk analizi ve tahmini\n• 📊 Deprem bilgileri ve haritalar\n• 🛡️ Güvenlik önlemleri\n• 🏛️ İstanbul erken uyarı sistemi\n• 📱 WhatsApp bildirimleri\n• 🗺️ Fay hatları\n\nLütfen bu konulardan birini sorun!'
        
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"[ERROR] Chatbot hatası: {e}")
        return jsonify({"response": "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."}), 500

@app.route('/api/set-alert', methods=['POST'])
def set_alert_settings():
    """ Kullanıcının konumunu ve bildirim telefon numarasını kaydeder ve onay mesajı gönderir. """
    try:
        global user_alerts
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Geçersiz istek. JSON verisi bekleniyor."}), 400
        
        try:
            lat = float(data.get('lat', 0))
            lon = float(data.get('lon', 0))
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Geçersiz koordinat formatı."}), 400
        
        # Koordinat kontrolü
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"status": "error", "message": "Geçersiz koordinatlar."}), 400
        
        number = data.get('number', '').strip() 
        
        if not number:
            return jsonify({"status": "error", "message": "Telefon numarası gereklidir."}), 400
        
        if not number.startswith('+'):
            return jsonify({"status": "error", "message": "Telefon numarası ülke kodu ile (+XX) başlamalıdır. Örnek: +90532xxxxxxx"}), 400
        
        # Konum bilgisini kalıcı hafızaya kaydet
        user_alerts[number] = {
            'lat': lat, 
            'lon': lon,
            'registered_at': datetime.now().isoformat()
        }
        save_user_alerts(user_alerts)
        
        print(f"Yeni WhatsApp Bildirim Ayarı Kaydedildi: {number} @ ({lat:.2f}, {lon:.2f})")
        
        # Google Maps konum linki oluştur
        location_url = f"https://www.google.com/maps?q={lat},{lon}"
        
        # Başarılı kayıt sonrası onay mesajı gönderme
        confirmation_body = f"🎉 YZ Destekli Deprem İzleme Sistemi'ne hoş geldiniz!\n"
        confirmation_body += f"✅ Bildirimler, konumunuz için başarıyla etkinleştirildi.\n"
        confirmation_body += f"📍 Kayıtlı Konum: {lat:.4f}, {lon:.4f}\n"
        confirmation_body += f"🔔 Bölgenizde (150 km içinde) M ≥ 5.0 deprem olursa size anında WhatsApp ile haber vereceğiz."
        
        # Onay mesajını göndermeyi dene
        send_success, send_error = send_whatsapp_notification(number, confirmation_body, location_url)
        if not send_success and send_error:
            print(f"[WARNING] WhatsApp bildirimi gönderilemedi: {send_error}")
            # Bildirim gönderilemese bile ayarları kaydet
        
        return jsonify({"status": "success", "message": "Bildirim ayarlarınız kaydedildi."})
    except ValueError as e:
        return jsonify({"status": "error", "message": f"Geçersiz veri formatı: {str(e)}"}), 400
    except Exception as e:
        print(f"[ERROR] Bildirim ayarları hatası: {e}")
        return jsonify({"status": "error", "message": f"Sunucu hatası: {str(e)}"}), 500

@app.route('/api/istanbul-alert', methods=['POST'])
def set_istanbul_alert():
    """ İstanbul için özel erken uyarı bildirimi kaydeder. Depremden ÖNCE mesaj gönderir. """
    try:
        global user_alerts
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Geçersiz istek. JSON verisi bekleniyor."}), 400
        
        number = data.get('number', '').strip()
        
        if not number:
            return jsonify({"status": "error", "message": "Telefon numarası gereklidir."}), 400
        
        if not number.startswith('+'):
            return jsonify({"status": "error", "message": "Telefon numarası ülke kodu ile (+XX) başlamalıdır. Örnek: +90532xxxxxxx"}), 400
        
        # İstanbul koordinatları (varsayılan olarak İstanbul merkez)
        istanbul_lat = ISTANBUL_COORDS['lat']
        istanbul_lon = ISTANBUL_COORDS['lon']
        
        # Kullanıcı özel koordinat vermişse onu kullan
        if data.get('lat') and data.get('lon'):
            try:
                lat = float(data.get('lat'))
                lon = float(data.get('lon'))
                if (-90 <= lat <= 90) and (-180 <= lon <= 180):
                    istanbul_lat = lat
                    istanbul_lon = lon
            except (ValueError, TypeError):
                pass  # Varsayılan İstanbul koordinatlarını kullan
        
        # İstanbul için özel işaretle
        user_alerts[number] = {
            'lat': istanbul_lat,
            'lon': istanbul_lon,
            'registered_at': datetime.now().isoformat(),
            'istanbul_alert': True  # İstanbul erken uyarı için özel işaret
        }
        save_user_alerts(user_alerts)
        
        print(f"İstanbul Erken Uyarı Bildirimi Kaydedildi: {number} @ ({istanbul_lat:.2f}, {istanbul_lon:.2f})")
        
        # Onay mesajı
        confirmation_body = f"🏛️ İSTANBUL ERKEN UYARI SİSTEMİ 🏛️\n"
        confirmation_body += f"✅ İstanbul için erken uyarı bildirimleri başarıyla etkinleştirildi!\n\n"
        confirmation_body += f"📍 Kayıtlı Konum: {istanbul_lat:.4f}, {istanbul_lon:.4f}\n\n"
        confirmation_body += f"🔔 SİSTEM NASIL ÇALIŞIR?\n"
        confirmation_body += f"• Yapay zeka destekli erken uyarı sistemi İstanbul çevresindeki deprem aktivitesini sürekli izler\n"
        confirmation_body += f"• Anormal aktivite tespit edildiğinde DEPREM ÖNCESİ size WhatsApp ile bildirim gönderilir\n"
        confirmation_body += f"• Uyarı seviyeleri: KRİTİK (0-24 saat), YÜKSEK (24-72 saat), ORTA (1 hafta)\n"
        confirmation_body += f"• Bildirimler otomatik olarak gönderilir, ek işlem yapmanıza gerek yok\n\n"
        confirmation_body += f"⚠️ Lütfen hazırlıklı olun ve acil durum planınızı gözden geçirin!"
        
        # Onay mesajını göndermeyi dene
        send_success, send_error = send_whatsapp_notification(number, confirmation_body)
        warning_message = None
        
        if not send_success and send_error:
            # HTTP 429 veya diğer hatalar için uyarı mesajı hazırla
            if "429" in send_error or "limit" in send_error.lower():
                warning_message = f"UYARI: Onay mesajı gönderilemedi. {send_error}"
            else:
                warning_message = f"UYARI: Onay mesajı gönderilemedi. {send_error}"
            print(f"[WARNING] {warning_message}")
        
        response_data = {
            "status": "success",
            "message": "İstanbul erken uyarı bildirimleri başarıyla kaydedildi. Deprem öncesi sinyaller tespit edildiğinde size WhatsApp ile bildirim gönderilecektir."
        }
        
        # Eğer mesaj gönderilemediyse uyarı ekle
        if warning_message:
            response_data["warning"] = warning_message
        
        return jsonify(response_data)
    except Exception as e:
        print(f"[ERROR] İstanbul bildirim ayarları hatası: {e}")
        return jsonify({"status": "error", "message": f"Sunucu hatası: {str(e)}"}), 500


# --- ARKA PLAN BİLDİRİM KONTROLÜ ---

def collect_training_data_continuously():
    """ Arka planda sürekli çalışır, eğitim verisi toplar ve günceller. """
    print("[VERI TOPLAMA] Sürekli veri toplama sistemi başlatıldı.")
    
    while True:
        try:
            # Her 30 dakikada bir veri topla
            time.sleep(1800)  # 30 dakika = 1800 saniye
            
            print(f"[VERI TOPLAMA] Yeni veri toplama başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Deprem verilerini çek
            earthquakes = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
            if not earthquakes:
                print("[VERI TOPLAMA] Veri çekilemedi, bir sonraki denemede tekrar denenilecek.")
                continue
            
            # Mevcut tarihsel veriyi yükle
            existing_data = []
            if os.path.exists(EARTHQUAKE_HISTORY_FILE):
                try:
                    with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    print(f"[VERI TOPLAMA] Mevcut veri yüklenemedi: {e}")
                    existing_data = []
            
            # Mevcut verilerin ID'lerini topla (duplicate kontrolü için)
            seen_ids = set()
            for record in existing_data:
                if 'features' in record:
                    # Şehir bazlı kayıtlar için
                    city = record.get('city', '')
                    lat = record.get('lat', 0)
                    lon = record.get('lon', 0)
                    timestamp = record.get('timestamp', 0)
                    record_id = f"{city}_{lat:.4f}_{lon:.4f}_{timestamp:.0f}"
                    seen_ids.add(record_id)
            
            # Yeni eğitim verisi oluştur (tüm şehirler için)
            new_training_data = []
            cities_processed = 0
            
            # Tüm 81 il için veri oluştur
            for city_name, city_data in TURKEY_CITIES.items():
                city_lat = city_data['lat']
                city_lon = city_data['lon']
                
                # Özellik çıkar
                features = extract_features(earthquakes, city_lat, city_lon, time_window_hours=168)  # Son 7 gün
                
                if features and features.get('count', 0) > 0:
                    # Risk skoru hesapla
                    risk_result = predict_earthquake_risk(earthquakes, city_lat, city_lon)
                    risk_score = risk_result.get('risk_score', 2.0)
                    
                    # Kayıt ID'si oluştur
                    current_time = time.time()
                    record_id = f"{city_name}_{city_lat:.4f}_{city_lon:.4f}_{current_time:.0f}"
                    
                    # Duplicate kontrolü (son 1 saat içinde aynı şehir için veri varsa atla)
                    recent_record_exists = False
                    for existing_record in existing_data[-100:]:  # Son 100 kayda bak
                        if existing_record.get('city') == city_name:
                            existing_timestamp = existing_record.get('timestamp', 0)
                            if current_time - existing_timestamp < 3600:  # 1 saat içinde
                                recent_record_exists = True
                                break
                    
                    if not recent_record_exists:
                        new_training_data.append({
                            'city': city_name,
                            'lat': city_lat,
                            'lon': city_lon,
                            'features': features,
                            'risk_score': risk_score,
                            'timestamp': current_time
                        })
                        cities_processed += 1
            
            # Yeni verileri mevcut veriye ekle
            if new_training_data:
                existing_data.extend(new_training_data)
                
                # Son 10,000 kaydı tut (dosya boyutunu kontrol altında tutmak için)
                if len(existing_data) > 10000:
                    existing_data = existing_data[-10000:]
                    print(f"[VERI TOPLAMA] Veri seti 10,000 kayıtla sınırlandırıldı (en eski kayıtlar silindi).")
                
                # Veriyi kaydet
                try:
                    with open(EARTHQUAKE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, ensure_ascii=False, indent=2)
                    
                    print(f"[VERI TOPLAMA] ✅ {cities_processed} şehir için {len(new_training_data)} yeni eğitim verisi eklendi. Toplam: {len(existing_data)} kayıt")
                except Exception as e:
                    print(f"[VERI TOPLAMA] Veri kaydedilemedi: {e}")
            else:
                print(f"[VERI TOPLAMA] Yeni veri bulunamadı (tüm şehirler için son 1 saat içinde veri mevcut).")
                
        except Exception as e:
            print(f"[VERI TOPLAMA] Hata: {e}")
            import traceback
            traceback.print_exc()
            # Hata olsa bile devam et
            continue

def check_for_big_earthquakes():
    """ Arka planda sürekli çalışır, M >= 5.0 deprem olup olmadığını kontrol eder. """
    global last_big_earthquake, user_alerts
    last_istanbul_alert_time = {}  # Her kullanıcı için son bildirim zamanı (spam önleme)
    
    while True:
        time.sleep(30)  # 30 saniyede bir kontrol et (daha hızlı tepki)

        try:
            earthquakes = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=1, timeout=30)
            if not earthquakes:
                continue
        except Exception:
            continue
        
        # TÜM TÜRKİYE İÇİN ERKEN UYARI KONTROLÜ (M ≥ 5.0 deprem riski)
        try:
            turkey_warnings = turkey_early_warning_system(earthquakes)
            
            # Her şehir için kontrol et
            for city_name, warning_data in turkey_warnings.items():
                alert_level = warning_data.get('alert_level', 'Normal')
                predicted_mag = warning_data.get('predicted_magnitude', 0)
                
                # M ≥ 5.0 riski varsa ve KRİTİK/YÜKSEK/ORTA seviyede bildirim gönder
                if alert_level in ['KRİTİK', 'YÜKSEK', 'ORTA'] and predicted_mag >= 5.0:
                    print(f"🚨 {city_name} ERKEN UYARI: {alert_level} - Tahmini M{predicted_mag:.1f} - {warning_data.get('time_to_event', '')}")
                    
                    # Kullanıcı verilerini tekrar yükle
                    user_alerts = load_user_alerts()
                    
                    # Bu şehir için kayıtlı kullanıcılara bildirim gönder
                    for number, coords in user_alerts.items():
                        city, _ = find_nearest_city(coords['lat'], coords['lon'])
                        
                        if city == city_name:
                            # Spam önleme
                            alert_key = f"{number}_{city_name}_{alert_level}"
                            current_time = time.time()
                            
                            if alert_key in last_istanbul_alert_time:
                                time_since_last = current_time - last_istanbul_alert_time[alert_key]
                                if time_since_last < 3600:  # 1 saat
                                    continue
                            
                            # Bildirim gönder
                            body = f"🚨 {city_name.upper()} ERKEN UYARI SİSTEMİ 🚨\n\n"
                            body += f"⚠️ M ≥ 5.0 DEPREM RİSKİ TESPİT EDİLDİ ⚠️\n\n"
                            body += f"Şehir: {city_name}\n"
                            body += f"Uyarı Seviyesi: {alert_level}\n"
                            body += f"Uyarı Skoru: {warning_data.get('alert_score', 0):.2f}/1.0\n"
                            body += f"Tahmini Büyüklük: M{predicted_mag:.1f}\n"
                            body += f"Tahmini Süre: {warning_data.get('time_to_event', 'Bilinmiyor')}\n"
                            body += f"Mesaj: {warning_data.get('message', 'Anormal aktivite tespit edildi')}\n"
                            
                            body += f"\n📊 DETAYLAR:\n"
                            body += f"• Son deprem sayısı: {warning_data.get('recent_earthquakes', 0)}\n"
                            body += f"• Anomali tespit edildi: {'Evet' if warning_data.get('anomaly_detected') else 'Hayır'}\n"
                            
                            body += f"\n⚠️ LÜTFEN HAZIRLIKLI OLUN:\n"
                            body += f"• Acil durum çantanızı hazırlayın\n"
                            body += f"• Güvenli yerleri belirleyin\n"
                            body += f"• Aile acil durum planınızı gözden geçirin\n"
                            body += f"• Sakin kalın ve hazırlıklı olun"
                            
                            send_success, send_error = send_whatsapp_notification(number, body)
                            if send_success:
                                last_istanbul_alert_time[alert_key] = current_time
                                print(f"✅ {city_name} erken uyarı bildirimi gönderildi: {number}")
                            else:
                                print(f"[ERROR] {city_name} bildirimi gönderilemedi ({number}): {send_error}")
        except Exception as e:
            print(f"[ERROR] Türkiye erken uyarı kontrolü hatası: {e}")
        
        # İstanbul erken uyarı kontrolü (eski sistem - geriye dönük uyumluluk)
        try:
            istanbul_warning = istanbul_early_warning_system(earthquakes)
            alert_level = istanbul_warning.get('alert_level', 'Normal')
            
            # KRİTİK, YÜKSEK veya ORTA seviyede bildirim gönder
            if alert_level in ['KRİTİK', 'YÜKSEK', 'ORTA']:
                print(f"🚨 İSTANBUL ERKEN UYARI: {alert_level} - {istanbul_warning.get('message', '')}")
                
                # Kullanıcı verilerini tekrar yükle (güncel olması için)
                user_alerts = load_user_alerts()
                
                # İstanbul için kayıtlı kullanıcılara bildirim gönder
                for number, coords in user_alerts.items():
                    # İstanbul erken uyarı için kayıtlı mı kontrol et
                    is_istanbul_alert = coords.get('istanbul_alert', False)
                    city, _ = find_nearest_city(coords['lat'], coords['lon'])
                    
                    # İstanbul'da veya İstanbul erken uyarı için kayıtlıysa
                    if city == 'İstanbul' or is_istanbul_alert:
                        # Spam önleme: Aynı seviye için 1 saat içinde tekrar bildirim gönderme
                        alert_key = f"{number}_{alert_level}"
                        current_time = time.time()
                        
                        if alert_key in last_istanbul_alert_time:
                            time_since_last = current_time - last_istanbul_alert_time[alert_key]
                            if time_since_last < 3600:  # 1 saat
                                continue  # Bu seviye için son 1 saatte bildirim gönderildi, atla
                        
                        # Bildirim gönder
                        body = f"🚨 İSTANBUL ERKEN UYARI SİSTEMİ 🚨\n\n"
                        body += f"⚠️ DEPREM ÖNCESİ UYARI ⚠️\n\n"
                        body += f"Uyarı Seviyesi: {alert_level}\n"
                        body += f"Uyarı Skoru: {istanbul_warning.get('alert_score', 0):.2f}/1.0\n"
                        body += f"Mesaj: {istanbul_warning.get('message', 'Anormal aktivite tespit edildi')}\n"
                        
                        if istanbul_warning.get('time_to_event'):
                            body += f"Tahmini Süre: {istanbul_warning['time_to_event']}\n"
                        
                        body += f"\n📊 DETAYLAR:\n"
                        body += f"• Son deprem sayısı: {istanbul_warning.get('recent_earthquakes', 0)}\n"
                        body += f"• Anomali tespit edildi: {'Evet' if istanbul_warning.get('anomaly_detected') else 'Hayır'}\n"
                        
                        body += f"\n⚠️ LÜTFEN HAZIRLIKLI OLUN:\n"
                        body += f"• Acil durum çantanızı hazırlayın\n"
                        body += f"• Güvenli yerleri belirleyin\n"
                        body += f"• Aile acil durum planınızı gözden geçirin\n"
                        body += f"• Sakin kalın ve hazırlıklı olun"
                        
                        send_success, send_error = send_whatsapp_notification(number, body)
                        if send_success:
                            last_istanbul_alert_time[alert_key] = current_time
                            print(f"✅ İstanbul erken uyarı bildirimi gönderildi: {number}")
                        else:
                            print(f"[ERROR] İstanbul bildirimi gönderilemedi ({number}): {send_error}")
        except Exception as e:
            print(f"[ERROR] İstanbul erken uyarı kontrolü hatası: {e}")

        for eq in earthquakes:
            mag = eq.get('mag', 0)
            
            if mag >= 5.0 and time.time() - last_big_earthquake['time'] > 1800:
                
                if eq.get('geojson') and eq['geojson'].get('coordinates'):
                    lon_eq, lat_eq = eq['geojson']['coordinates']
                    
                    print(f"!!! YENİ BÜYÜK DEPREM TESPİT EDİLDİ: M{mag} @ ({lat_eq:.2f}, {lon_eq:.2f})")
                    last_big_earthquake = {'mag': mag, 'time': time.time()}

                    # Kullanıcı verilerini tekrar yükle (güncel olması için)
                    user_alerts = load_user_alerts()
                    
                    for number, coords in user_alerts.items():
                        distance = haversine(coords['lat'], coords['lon'], lat_eq, lon_eq)
                        
                        if distance < 150:
                            deprem_time_str = f"{eq.get('date')} {eq.get('time')}"
                            
                            # Hasar tahmini yap
                            depth = eq.get('depth', 10)
                            damage_info = calculate_damage_estimate(mag, depth, distance)
                            
                            # Google Maps konum linki (deprem merkezi)
                            eq_location_url = f"https://www.google.com/maps?q={lat_eq},{lon_eq}"
                            
                            # Kullanıcı konum linki
                            user_location_url = f"https://www.google.com/maps?q={coords['lat']},{coords['lon']}"
                            
                            body = f"🚨 ACİL DEPREM UYARISI 🚨\n"
                            body += f"Büyüklük: M{mag:.1f}\n"
                            body += f"Yer: {eq.get('location', 'Bilinmiyor')}\n"
                            body += f"Saat: {deprem_time_str}\n"
                            body += f"Derinlik: {depth} km\n"
                            body += f"Mesafe: {distance:.1f} km (Konumunuza yakın)\n\n"
                            body += f"📊 HASAR TAHMİNİ:\n"
                            body += f"Seviye: {damage_info['level']}\n"
                            body += f"Skor: {damage_info['damage_score']}/100\n"
                            body += f"Açıklama: {damage_info['description']}\n\n"
                            body += f"📍 Deprem Merkezi: {eq_location_url}\n"
                            body += f"📍 Sizin Konumunuz: {user_location_url}\n\n"
                            body += f"⚠️ Lütfen güvende kalın ve acil durum planınızı uygulayın!"
                            
                            send_success, send_error = send_whatsapp_notification(number, body)
                            if not send_success:
                                print(f"[ERROR] Büyük deprem bildirimi gönderilemedi ({number}): {send_error}")

# Arka plan iş parçacıklarını başlat

# 1. Büyük deprem kontrolü (30 saniyede bir)
alert_thread = Thread(target=check_for_big_earthquakes)
alert_thread.daemon = True 
alert_thread.start()

# 2. Sürekli veri toplama (30 dakikada bir)
data_collection_thread = Thread(target=collect_training_data_continuously)
data_collection_thread.daemon = True
data_collection_thread.start()
print("[SISTEM] Sürekli veri toplama sistemi başlatıldı (her 30 dakikada bir).")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Flask Sunucusu Başlatıldı: http://127.0.0.1:{port}/api/risk")
    app.run(host='0.0.0.0', port=port)