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
from textblob import TextBlob

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

# --- META WHATSAPP BUSINESS API AYARLARI ---
# Meta WhatsApp Business API için gerekli bilgiler (kalıcı token kullanılmalı)
# ChatGPT formatı: META_WA_TOKEN (öncelikli) veya META_WHATSAPP_ACCESS_TOKEN (geriye dönük uyumluluk)
META_WHATSAPP_ACCESS_TOKEN = os.environ.get("META_WA_TOKEN") or os.environ.get("META_WHATSAPP_ACCESS_TOKEN")
META_WHATSAPP_PHONE_NUMBER_ID = os.environ.get("META_WHATSAPP_PHONE_NUMBER_ID", "833412653196098")
META_WHATSAPP_API_VERSION = os.environ.get("META_WHATSAPP_API_VERSION", "v22.0")
META_WHATSAPP_TEST_NUMBER = os.environ.get("META_WHATSAPP_TEST_NUMBER", "+15551679784")  # Test numarası (From)
META_WHATSAPP_API_URL = f"https://graph.facebook.com/{META_WHATSAPP_API_VERSION}/{META_WHATSAPP_PHONE_NUMBER_ID}/messages"

# Meta WhatsApp API kullanılabilir mi kontrolü
USE_META_WHATSAPP = bool(META_WHATSAPP_ACCESS_TOKEN and META_WHATSAPP_PHONE_NUMBER_ID)

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

# Chatbot context memory (session bazlı)
chatbot_contexts = {}  # {session_id: {'history': [], 'user_mood': None, 'topics': []}}

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

def send_whatsapp_via_meta_api(recipient_number, body, location_url=None):
    """
    Meta WhatsApp Business API ile serbest metin mesajı gönderir.
    Kullanıcı daha önce session açmışsa (24 saat içinde) serbest metin gönderebilir.
    Returns: (success: bool, error_message: str veya None)
    """
    if not USE_META_WHATSAPP:
        return False, "Meta WhatsApp API ayarları yapılmamış"
    
    try:
        # Numara formatını düzelt (ülke kodu ile, + işareti olmadan)
        clean_number = recipient_number.replace('+', '').replace(' ', '').replace('-', '')
        
        # Konum linki varsa mesaja ekle
        if location_url:
            body += f"\n\n📍 Konum: {location_url}"
        
        # Meta WhatsApp API payload
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "text",
            "text": {
                "body": body
            }
        }
        
        # Headers
        headers = {
            "Authorization": f"Bearer {META_WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # API çağrısı
        response = requests.post(
            META_WHATSAPP_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Meta WhatsApp mesajı gönderildi: {recipient_number}")
            print(f"[OK] Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
            return True, None
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
            error_code = error_data.get('error', {}).get('code', response.status_code)
            
            print(f"[ERROR] Meta WhatsApp API hatası: {error_msg} (Code: {error_code})")
            
            # Session açılmamış hatası (kullanıcı henüz mesaj atmamış)
            if error_code == 131047 or "session" in error_msg.lower() or "24 hour" in error_msg.lower():
                return False, "SESSION_REQUIRED"  # Özel hata kodu
            
            return False, error_msg
            
    except requests.exceptions.Timeout:
        print("[ERROR] Meta WhatsApp API timeout")
        return False, "API timeout"
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Meta WhatsApp API beklenmeyen hata: {error_msg}")
        return False, f"Beklenmeyen hata: {error_msg}"

def send_sms_via_twilio(recipient_number, body):
    """
    Twilio SMS API ile SMS gönderir (fallback için).
    Returns: (success: bool, error_message: str veya None)
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return False, "Twilio SMS ayarları yapılmamış"
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Numara formatını düzelt
        if not recipient_number.startswith('+'):
            recipient_number = '+' + recipient_number.lstrip('0')
        
        # SMS gönder (Twilio'nun normal SMS numarası gerekli, WhatsApp numarası değil)
        # Burada Twilio'nun SMS numarasını kullanmanız gerekir (TWILIO_SMS_FROM_NUMBER)
        # Şimdilik Twilio WhatsApp numarasını kullanıyoruz (test için)
        
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_NUMBER.replace('whatsapp:', ''),  # SMS için whatsapp: prefix'i kaldır
            to=recipient_number
        )
        print(f"[OK] SMS gönderildi: {recipient_number}, SID: {message.sid}")
        return True, None
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] SMS gönderme hatası: {error_msg}")
        return False, error_msg

def send_whatsapp_notification(recipient_number, body, location_url=None):
    """
    WhatsApp mesajı gönderir. Önce Meta WhatsApp API dener, başarısız olursa SMS fallback.
    Hybrid sistem: WhatsApp + SMS fallback
    Returns: (success: bool, error_message: str veya None)
    """
    # ÖNCE Meta WhatsApp API dene (serbest metin - session açılmışsa)
    if USE_META_WHATSAPP:
        print("[INFO] Meta WhatsApp API deneniyor...")
        success, error = send_whatsapp_via_meta_api(recipient_number, body, location_url)
        
        if success:
            return True, None
        
        # Session açılmamışsa SMS fallback
        if error == "SESSION_REQUIRED":
            print("[INFO] WhatsApp session açılmamış, SMS fallback deneniyor...")
            sms_success, sms_error = send_sms_via_twilio(recipient_number, body)
            if sms_success:
                return True, None
            return False, f"WhatsApp session gerekli ve SMS gönderilemedi: {sms_error}"
        
        # Diğer hatalarda SMS fallback
        print(f"[WARNING] Meta WhatsApp başarısız ({error}), SMS fallback deneniyor...")
        sms_success, sms_error = send_sms_via_twilio(recipient_number, body)
        if sms_success:
            return True, None
        return False, f"WhatsApp hatası: {error}, SMS hatası: {sms_error}"
    
    # Meta WhatsApp yoksa eski Twilio sistemini kullan
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

@app.route('/api/dataset-count', methods=['GET'])
def dataset_count():
    """ Eğitimde kullanılan veri seti sayısını döndürür. """
    try:
        if not os.path.exists(EARTHQUAKE_HISTORY_FILE):
            return jsonify({
                "total_records": 0,
                "city_based_records": 0,
                "kandilli_raw_records": 0,
                "message": "Henüz veri seti oluşturulmamış."
            })
        
        with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        if not history:
            return jsonify({
                "total_records": 0,
                "city_based_records": 0,
                "kandilli_raw_records": 0,
                "message": "Veri seti boş."
            })
        
        # Veri tiplerini say
        city_based = 0  # Şehir bazlı eğitim verileri (features içeren)
        kandilli_raw = 0  # Kandilli'den çekilen ham deprem verileri (geojson içeren)
        
        for record in history:
            if 'features' in record and 'risk_score' in record:
                city_based += 1
            elif 'geojson' in record and record.get('source') == 'kandilli':
                kandilli_raw += 1
        
        return jsonify({
            "total_records": len(history),
            "city_based_records": city_based,
            "kandilli_raw_records": kandilli_raw,
            "message": f"Toplam {len(history)} kayıt: {city_based} şehir bazlı eğitim verisi, {kandilli_raw} Kandilli ham deprem verisi"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dataset-info', methods=['GET'])
def dataset_info():
    """ Eğitimde kullanılan güncel veri seti bilgilerini döndürür. """
    try:
        # Veri seti dosyasını kontrol et
        if not os.path.exists(EARTHQUAKE_HISTORY_FILE):
            return jsonify({
                "status": "no_data",
                "message": "Henüz veri seti oluşturulmamış.",
                "total_records": 0,
                "file_size_kb": 0,
                "cities_count": 0,
                "date_range": None,
                "last_update": None,
                "statistics": {}
            })
        
        # Dosya bilgileri
        file_size = os.path.getsize(EARTHQUAKE_HISTORY_FILE)
        file_size_kb = round(file_size / 1024, 2)
        
        # Veri setini yükle
        with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        if not history or len(history) == 0:
            return jsonify({
                "status": "empty",
                "message": "Veri seti boş.",
                "total_records": 0,
                "file_size_kb": file_size_kb,
                "cities_count": 0,
                "date_range": None,
                "last_update": None,
                "statistics": {}
            })
        
        # İstatistikler
        total_records = len(history)
        cities = set()
        timestamps = []
        risk_scores = []
        
        for record in history:
            if 'city' in record:
                cities.add(record['city'])
            if 'timestamp' in record:
                timestamps.append(record['timestamp'])
            if 'risk_score' in record:
                risk_scores.append(record['risk_score'])
        
        # Tarih aralığı
        date_range = None
        if timestamps:
            min_timestamp = min(timestamps)
            max_timestamp = max(timestamps)
            min_date = datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            max_date = datetime.fromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            date_range = {
                "first_record": min_date,
                "last_record": max_date,
                "days_span": round((max_timestamp - min_timestamp) / 86400, 1)
            }
        
        # Son güncelleme
        last_update = None
        if timestamps:
            last_timestamp = max(timestamps)
            last_update = datetime.fromtimestamp(last_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # Risk skoru istatistikleri
        risk_stats = {}
        if risk_scores:
            risk_stats = {
                "min": round(min(risk_scores), 2),
                "max": round(max(risk_scores), 2),
                "mean": round(sum(risk_scores) / len(risk_scores), 2),
                "median": round(sorted(risk_scores)[len(risk_scores) // 2], 2) if risk_scores else 0
            }
        
        # Şehir bazlı istatistikler
        city_counts = {}
        for record in history:
            city = record.get('city', 'Bilinmeyen')
            city_counts[city] = city_counts.get(city, 0) + 1
        
        # En çok veri olan şehirler (top 10)
        top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return jsonify({
            "status": "success",
            "total_records": total_records,
            "file_size_kb": file_size_kb,
            "cities_count": len(cities),
            "date_range": date_range,
            "last_update": last_update,
            "statistics": {
                "risk_score": risk_stats,
                "top_cities": [{"city": city, "count": count} for city, count in top_cities],
                "total_cities": len(cities)
            },
            "model_status": {
                "model_exists": os.path.exists(RISK_PREDICTION_MODEL_FILE),
                "model_file_size_kb": round(os.path.getsize(RISK_PREDICTION_MODEL_FILE) / 1024, 2) if os.path.exists(RISK_PREDICTION_MODEL_FILE) else 0
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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
    """ Gelişmiş AI destekli deprem asistanı chatbot endpoint'i. """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Üzgünüm, mesajınızı anlayamadım. Lütfen tekrar deneyin."}), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({"response": "Lütfen bir mesaj yazın."}), 400
        
        # Session ID (frontend'den gelirse kullan, yoksa oluştur)
        session_id = data.get('session_id', 'default')
        if session_id not in chatbot_contexts:
            chatbot_contexts[session_id] = {
                'history': [],
                'user_mood': None,
                'topics': [],
                'last_interaction': time.time()
            }
        
        context = chatbot_contexts[session_id]
        
        # Ruh hali analizi (sentiment analysis)
        try:
            blob = TextBlob(message)
            sentiment_score = blob.sentiment.polarity  # -1 (negatif) ile +1 (pozitif) arası
            
            if sentiment_score > 0.3:
                mood = 'pozitif'
            elif sentiment_score < -0.3:
                mood = 'negatif'
            else:
                mood = 'nötr'
            
            context['user_mood'] = mood
        except:
            mood = 'nötr'
        
        message_lower = message.lower()
        
        # Konuşma geçmişine ekle
        context['history'].append({
            'user': message,
            'timestamp': time.time(),
            'mood': mood
        })
        
        # Son 10 mesajı tut
        if len(context['history']) > 10:
            context['history'] = context['history'][-10:]
        
        # Gelişmiş rule-based AI - Öncelikli pattern matching (daha spesifik önce)
        # ÖNEMLİ: Daha spesifik pattern'ler önce kontrol edilmeli
        
        # Öncelik 1: Ruh hali ve duygusal destek (en önemli - önce kontrol edilmeli)
        if any(word in message_lower for word in ['korku', 'korkuyorum', 'korkuyor', 'endişe', 'endişeliyim', 'kaygı', 'kaygılı', 'stres', 'stresli', 'panik', 'panikliyim', 'korkarım', 'korktum', 'korktuk']):
            response_text = '💚 KORKUNUZU ANLIYORUM - DESTEK REHBERİ:\n\n'
            response_text += '😔 Deprem konusunda korku ve endişe duymanız çok normal. Bu duyguları yaşamak insan doğasının bir parçasıdır.\n\n'
            response_text += '🛡️ KORKUNUZU AZALTMAK İÇİN:\n'
            response_text += '1. HAZIRLIK YAPIN: Hazırlık yapmak korkunuzu azaltır ve güvenlik hissi verir\n'
            response_text += '   • Acil durum çantası hazırlayın\n'
            response_text += '   • Aile acil durum planı yapın\n'
            response_text += '   • Güvenli yerleri belirleyin\n\n'
            response_text += '2. BİLGİLENİN: Doğru bilgi kaynaklarından bilgi alın\n'
            response_text += '   • Bu sistemden risk analizi yapın\n'
            response_text += '   • AFAD ve Kandilli gibi resmi kaynakları takip edin\n'
            response_text += '   • Yanlış bilgilerden uzak durun\n\n'
            response_text += '3. AİLE İLE KONUŞUN: Duygularınızı paylaşın\n'
            response_text += '   • Aile üyelerinizle acil durum planınızı gözden geçirin\n'
            response_text += '   • Çocuklarınızla deprem hakkında yaşlarına uygun konuşun\n\n'
            response_text += '4. PROFESYONEL DESTEK: Gerekirse destek alın\n'
            response_text += '   • Aşırı kaygı durumunda psikolog desteği alabilirsiniz\n'
            response_text += '   • AFAD ve Kızılay psikososyal destek hizmetleri var\n\n'
            response_text += '💪 HAZIRLIK = GÜVENLİK = HUZUR\n'
            response_text += 'Hazırlık yapmak sizi güçlendirir ve korkunuzu azaltır. Size nasıl yardımcı olabilirim?'
        
        # Öncelik 2: Deprem anında ne yapmalı (çok spesifik)
        elif any(phrase in message_lower for phrase in ['deprem anında', 'deprem sırasında', 'deprem olduğunda', 'deprem olursa', 'deprem sırası', 'deprem anı', 'deprem sırası ne yapmalı', 'deprem anında ne yapmalı']):
            response_text = '🚨 DEPREM ANINDA YAPILACAKLAR (ÇÖK-KAPAN-TUTUN):\n\n'
            response_text += '1️⃣ ÇÖK: Hemen yere çökün\n'
            response_text += '   • Ayakta durmayın\n'
            response_text += '   • Yere çömelin\n\n'
            response_text += '2️⃣ KAPAN: Başınızı ve boynunuzu koruyun\n'
            response_text += '   • Ellerinizle başınızı ve boynunuzu koruyun\n'
            response_text += '   • Mümkünse masa altına girin\n'
            response_text += '   • Yoksa kolon yanına geçin\n\n'
            response_text += '3️⃣ TUTUN: Sağlam bir yere tutunun\n'
            response_text += '   • Masa bacağına tutunun\n'
            response_text += '   • Sarsıntı bitene kadar tutun\n\n'
            response_text += '⚠️ DEPREM ANINDA YAPILMAMASI GEREKENLER:\n'
            response_text += '❌ Asansör kullanmayın\n'
            response_text += '❌ Merdivenlerden uzak durun\n'
            response_text += '❌ Pencerelerden, dolaplardan, asılı eşyalardan uzak durun\n'
            response_text += '❌ Balkonlardan atlamayın\n'
            response_text += '❌ Binalardan dışarı çıkmaya çalışmayın\n\n'
            response_text += '💡 Sarsıntı bitene kadar ÇÖK-KAPAN-TUTUN pozisyonunda kalın!'
        
        # Öncelik 3: Diğer spesifik sorular
        elif any(word in message_lower for word in ['iyi hissetmemi sağla', 'iyi hisset', 'rahatlat', 'sakinleştir', 'huzur', 'güven']):
            response_text = '💚 SİZİ RAHATLATMAK İÇİN:\n\n'
            response_text += '😊 Öncelikle şunu bilin: Hazırlık yapmak sizi güçlendirir!\n\n'
            response_text += '✅ YAPABİLECEKLERİNİZ:\n'
            response_text += '1. Acil durum çantanızı hazırlayın (bu sizi güvende hissettirir)\n'
            response_text += '2. Aile ile acil durum planı yapın\n'
            response_text += '3. Bu sistemden risk analizi yapın (bilgi güven verir)\n'
            response_text += '4. Doğru bilgi kaynaklarından bilgi alın\n'
            response_text += '5. Nefes egzersizleri yapın (kaygı için)\n\n'
            response_text += '🛡️ HAZIRLIK = GÜVENLİK = HUZUR\n'
            response_text += 'Hazırlık yapmak endişelerinizi azaltır ve sizi güçlendirir.\n\n'
            response_text += 'Size nasıl yardımcı olabilirim? Risk analizi yapmak ister misiniz?'
        
        # Gelişmiş rule-based AI - Çoklu anahtar kelime desteği ve gerçek zamanlı veri
        responses = {
            # Selamlama
            ('merhaba', 'selam', 'hey', 'hi', 'hello', 'günaydın', 'iyi günler', 'iyi akşamlar'): 'Merhaba! 👋 Ben deprem asistanınız. Deprem güvenliği, risk analizi ve erken uyarı sistemi hakkında size yardımcı olabilirim. Nasıl yardımcı olabilirim?',
            
            # Risk analizi
            ('risk', 'risk analizi', 'risk tahmini', 'tehlike', 'güvenli mi', 'riskli mi', 'risk nedir', 'risk skoru'): '🔍 Risk analizi için:\n• Haritadaki "Risk Analizi" bölümünü kullanabilirsiniz\n• "Konumum İçin Risk Tahmini Yap" butonu ile kişisel analiz yapabilirsiniz\n• "İl Bazında Risk Analizi" ile tüm illerin risk durumunu görebilirsiniz\n\nSistem son depremlere ve aktif fay hatlarına göre analiz yapar.',
            
            # Deprem bilgileri (genel - spesifik değil)
            ('deprem', 'depremler', 'son deprem', 'deprem listesi', 'deprem haritası', 'bugün deprem', 'son 24 saat', 'yakın zamanda'): '📊 Deprem bilgileri için:\n• "Son 1 Gün Depremler & Aktif Fay Hatları" haritasından son depremleri görebilirsiniz\n• Haritada deprem büyüklüğü, konum ve tarih bilgileri görüntülenir\n• İstanbul için özel erken uyarı sistemi mevcuttur',
            
            # Güvenlik (genel - spesifik değil)
            ('güvenlik', 'güvenli', 'nasıl korunur', 'önlem', 'hazırlık', 'deprem öncesi', 'deprem sonrası', 'çök kapan tutun', 'acil durum', 'hazırlık çantası', 'acil çanta'): '🛡️ DEPREM GÜVENLİĞİ:\n\n📌 DEPREM ÖNCESİ:\n• Acil durum çantası hazırlayın (su, yiyecek, ilaç, fener, pil, radyo)\n• Aile acil durum planı yapın\n• Güvenli yerleri belirleyin (masa altı, kolon yanı)\n• Mobilyaları sabitleyin\n• Gaz ve elektrik vanalarının yerini öğrenin\n\n📌 DEPREM SIRASINDA:\n• ÇÖK: Yere çökün\n• KAPAN: Başınızı ve boynunuzu koruyun\n• TUTUN: Sağlam bir yere tutunun\n• Pencerelerden, dolaplardan, asılı eşyalardan uzak durun\n• Asansör kullanmayın\n• Merdivenlerden uzak durun\n\n📌 DEPREM SONRASI:\n• Gaz, elektrik ve su vanalarını kapatın\n• Açık alanlara çıkın\n• Binalara girmeyin\n• Acil durum çantanızı alın\n• Telefon hatlarını gereksiz kullanmayın',
            
            # İstanbul
            ('istanbul', 'istanbul uyarı', 'istanbul erken uyarı', 'istanbul risk', 'istanbul güvenli mi', 'istanbul deprem'): '🏛️ İSTANBUL ERKEN UYARI SİSTEMİ:\n• İstanbul için özel gelişmiş yapay zeka destekli erken uyarı sistemi\n• "İstanbul Erken Uyarı Durumunu Kontrol Et" butonundan kontrol edebilirsiniz\n• Sistem deprem öncesi sinyalleri tespit ederek önceden uyarı verir\n• Uyarı seviyeleri: KRİTİK (0-24 saat), YÜKSEK (24-72 saat), ORTA (1 hafta), DÜŞÜK\n• WhatsApp bildirimleri ile anında uyarı alabilirsiniz',
            
            # Fay hatları
            ('fay', 'fay hattı', 'fay hatları', 'kaf', 'daf', 'aktif fay', 'kuzey anadolu', 'doğu anadolu', 'ege graben'): '🗺️ TÜRKİYE AKTİF FAY HATLARI:\n• Kuzey Anadolu Fay Hattı (KAF) - En aktif fay hattı\n• Doğu Anadolu Fay Hattı (DAF)\n• Ege Graben Sistemi\n• Batı Anadolu Fay Sistemi\n\nHaritada "Son 1 Gün Depremler & Aktif Fay Hatları" bölümünden tüm fay hatlarını görebilirsiniz. Fay hatlarına yakın bölgeler daha yüksek risk taşır.',
            
            # Hasar tahmini
            ('hasar', 'hasar tahmini', 'hasar analizi', 'yıkım', 'zarar', 'bina hasarı', 'yapı hasarı'): '🏙️ HASAR TAHMİNİ:\n• "İl Bazında Risk Analizi" bölümünden tüm illerin risk durumunu görebilirsiniz\n• Sistem son depremlere ve fay hatlarına yakınlığa göre analiz yapar\n• Her il için risk skoru, seviye ve detaylı faktörler gösterilir\n• Bina yapısı analizi (güçlendirilmiş/normal/zayıf) dahil\n• Hasar skoru 0-100 arası hesaplanır',
            
            # Bildirim
            ('bildirim', 'uyarı', 'whatsapp', 'mesaj', 'sms', 'alarm', 'nasıl bildirim alırım', 'bildirim ayarla'): '📱 WHATSAPP BİLDİRİMLERİ:\n• "Acil Durum WhatsApp Bildirim Ayarları" bölümünden ayarlayabilirsiniz\n• Konumunuzu belirleyin\n• WhatsApp numaranızı girin (ülke kodu ile: +90...)\n• M ≥ 5.0 depremlerde 150 km içindeyse otomatik bildirim alırsınız\n• İstanbul için özel erken uyarı bildirimleri mevcuttur\n• Twilio WhatsApp Sandbox\'a katılmanız gerekiyor (ücretsiz)',
            
            # Yardım
            ('yardım', 'help', 'nasıl kullanılır', 'kullanım', 'ne yapabilirsin', 'komutlar', 'özellikler', 'neler yapabilir'): '💡 NASIL KULLANILIR:\n\n1️⃣ Risk Analizi: Konumunuzu belirleyip risk tahmini yapın\n2️⃣ Deprem Haritası: Son depremleri ve fay hatlarını görüntüleyin\n3️⃣ İl Bazında Analiz: Tüm illerin risk durumunu kontrol edin\n4️⃣ İstanbul Uyarı: İstanbul için erken uyarı durumunu kontrol edin\n5️⃣ Bildirimler: WhatsApp bildirimlerini aktifleştirin\n6️⃣ Türkiye Erken Uyarı: Tüm Türkiye için M≥5.0 deprem uyarıları\n\nBaşka bir sorunuz varsa sorabilirsiniz!',
            
            # Sistem bilgisi
            ('nasıl çalışır', 'sistem', 'yapay zeka', 'ml', 'makine öğrenmesi', 'algoritma', 'model', 'ai', 'yz'): '🤖 SİSTEM NASIL ÇALIŞIR:\n• Kandilli Rasathanesi verilerini kullanır\n• Gerçek zamanlı deprem analizi yapar\n• Makine öğrenmesi modelleri (Random Forest, XGBoost, LightGBM) ile risk tahmini\n• Ensemble learning ile %82 doğruluk\n• Anomali tespiti ile olağandışı aktivite tespit eder\n• Aktif fay hatlarına yakınlık analizi\n• 17 farklı özellik (feature) ile analiz',
            
            # Teşekkür
            ('teşekkür', 'teşekkürler', 'sağol', 'sağolun', 'thanks', 'thank you', 'eyvallah', 'mükemmel'): 'Rica ederim! 😊 Başka bir sorunuz varsa çekinmeyin. Deprem güvenliğiniz için her zaman buradayım!',
            
            # Genel bilgi
            ('kandilli', 'veri', 'kaynak', 'nereden', 'veri kaynağı', 'api'): '📡 VERİ KAYNAĞI:\n• Kandilli Rasathanesi ve Deprem Araştırma Enstitüsü\n• Gerçek zamanlı deprem verileri\n• API: api.orhanaydogdu.com.tr\n• Veriler sürekli güncellenir\n• Son 1 gün içindeki tüm depremler analiz edilir',
            
            # Büyüklük soruları
            ('büyüklük', 'magnitude', 'richter', 'm', 'kaç şiddet', 'şiddet', 'ölçek'): '📏 DEPREM BÜYÜKLÜĞÜ:\n• Richter ölçeği kullanılır (M2.0 - M9.0+)\n• M2.0-3.9: Çok küçük (hissedilmez)\n• M4.0-4.9: Küçük (hafif sallanma)\n• M5.0-5.9: Orta (hasar yapabilir)\n• M6.0-6.9: Büyük (ciddi hasar)\n• M7.0+: Çok büyük (yıkıcı)\n\nSistem M≥5.0 depremler için özel uyarı verir.',
            
            # Derinlik soruları
            ('derinlik', 'derin', 'sığ', 'yer kabuğu', 'odak derinliği'): '⛰️ DEPREM DERİNLİĞİ:\n• Sığ depremler (0-70 km): Daha fazla hasar verir\n• Orta derinlik (70-300 km): Orta hasar\n• Derin depremler (300+ km): Daha az hasar\n\nSistem derinlik analizi yaparak hasar tahmini yapar.',
            
            # Erken uyarı
            ('erken uyarı', 'uyarı sistemi', 'önceden haber', 'tahmin', 'önceden bilmek'): '🚨 ERKEN UYARI SİSTEMİ:\n• İstanbul için özel gelişmiş sistem\n• Deprem öncesi sinyalleri tespit eder\n• Anomali tespiti ile olağandışı aktivite uyarısı\n• Uyarı seviyeleri: KRİTİK, YÜKSEK, ORTA\n• WhatsApp ile anında bildirim\n• Makine öğrenmesi ile yüksek doğruluk',
            
            # İl soruları - Gerçek zamanlı veri ile
            ('ankara', 'izmir', 'bursa', 'antalya', 'adana', 'gaziantep', 'konya', 'şehir', 'il', 'hangi il', 'il durumu', 'şehir durumu', 'il bazlı', 'şehir bazlı'): None,  # Özel işlem gerekiyor
            
            # Veri seti bilgileri
            ('veri seti', 'dataset', 'eğitim verisi', 'veri seti bilgileri', 'veri durumu', 'model verisi', 'eğitim durumu', 'veri istatistikleri'): None,  # Özel işlem gerekiyor
            
            # Hava durumu
            ('hava durumu', 'hava', 'weather', 'sıcaklık', 'yağmur', 'kar', 'rüzgar', 'günlük hava', 'bugün hava'): None,  # Özel işlem gerekiyor
            
            # Acil durum - Genişletilmiş
            ('acil durum', 'acil', 'ne yapmalıyım', 'deprem anında', 'deprem oldu', 'şimdi ne yapmalı', 'acil çıkış', 'güvenli yer', 'toplanma alanı', 'acil telefon', '112', 'afad', 'kızılay'): '🚨 ACİL DURUM REHBERİ:\n\n📞 ACİL TELEFONLAR:\n• 112 - Acil Çağrı Merkezi\n• 110 - İtfaiye\n• 155 - Polis\n• 156 - Jandarma\n• AFAD: 1222\n• Kızılay: 444 0 186\n\n🏃 DEPREM ANINDA:\n• ÇÖK-KAPAN-TUTUN pozisyonu alın\n• Sağlam bir masa/sehpa altına girin\n• Pencerelerden, dolaplardan uzak durun\n• Asansör kullanmayın\n• Merdivenlerden uzak durun\n• Balkonlardan atlamayın\n\n🏃 DEPREM SONRASI:\n• Gaz, elektrik, su vanalarını kapatın\n• Açık alanlara çıkın (toplanma alanlarına)\n• Binalara girmeyin\n• Acil durum çantanızı alın\n• Telefon hatlarını gereksiz kullanmayın\n• Radyo dinleyin (AFAD, TRT)\n\n📦 ACİL DURUM ÇANTASI:\n• Su (3-4 litre)\n• Konserve yiyecekler\n• İlk yardım malzemeleri\n• Fener, pil, radyo\n• Önemli belgeler (fotokopi)\n• Nakit para\n• Battaniye\n• Hijyen malzemeleri',
            
            # Anomali
            ('anomali', 'olağandışı', 'normal değil', 'garip', 'anormal'): '🔍 ANOMALİ TESPİTİ:\n• Isolation Forest modeli ile anomali tespiti\n• Olağandışı deprem aktivitesi tespit edilir\n• Yüksek aktivite, büyük depremler, yakın mesafe kontrol edilir\n• Anomali tespit edildiğinde erken uyarı verilir\n• İstanbul erken uyarı sisteminde kullanılır',
            
            # Harita
            ('harita', 'görselleştirme', 'görsel', 'map', 'haritada'): '🗺️ HARİTA ÖZELLİKLERİ:\n• İki harita mevcut:\n  1. YZ Risk Analizi - Risk bölgeleri\n  2. Son 1 Gün Depremler & Aktif Fay Hatları\n• Depremler büyüklüğe göre renklendirilir\n• Fay hatları kırmızı kesikli çizgi ile gösterilir\n• Marker\'lara tıklayarak detaylı bilgi alabilirsiniz',
        }
        
        # Çoklu anahtar kelime eşleştirme
        response_text = None
        matched_keywords = []
        needs_special_processing = False
        special_type = None
        
        for keywords, response in responses.items():
            for keyword in keywords:
                if keyword in message_lower:
                    if response is None:  # Özel işlem gerekiyor
                        needs_special_processing = True
                        # Hangi özel işlem tipi?
                        if keyword in ['veri seti', 'dataset', 'eğitim verisi', 'veri seti bilgileri', 'veri durumu', 'model verisi', 'eğitim durumu', 'veri istatistikleri']:
                            special_type = 'dataset_info'
                        elif keyword in ['hava durumu', 'hava', 'weather', 'sıcaklık', 'yağmur', 'kar', 'rüzgar', 'günlük hava', 'bugün hava']:
                            special_type = 'weather'
                        elif keyword in ['ankara', 'izmir', 'bursa', 'antalya', 'adana', 'gaziantep', 'konya', 'şehir', 'il', 'hangi il', 'il durumu', 'şehir durumu', 'il bazlı', 'şehir bazlı']:
                            special_type = 'city_earthquake_status'
                    else:
                        response_text = response
                    matched_keywords.append(keyword)
                    break
            if response_text or needs_special_processing:
                break
        
        # Eğer eşleşme yoksa, benzer kelimeleri kontrol et
        if not response_text:
            # Kısmi eşleşme ve genişletilmiş pattern matching
            similar_patterns = {
                'risk': responses[('risk', 'risk analizi', 'risk tahmini', 'tehlike', 'güvenli mi', 'riskli mi', 'risk nedir', 'risk skoru')],
                'deprem': responses[('deprem', 'depremler', 'son deprem', 'deprem listesi', 'deprem haritası', 'bugün deprem', 'son 24 saat', 'yakın zamanda')],
                'güven': responses[('güvenlik', 'güvenli', 'ne yapmalı', 'nasıl korunur', 'önlem', 'hazırlık', 'deprem sırasında', 'deprem öncesi', 'deprem sonrası', 'çök kapan tutun', 'acil durum', 'hazırlık çantası', 'acil çanta')],
                'istanbul': responses[('istanbul', 'istanbul uyarı', 'istanbul erken uyarı', 'istanbul risk', 'istanbul güvenli mi', 'istanbul deprem')],
                'fay': responses[('fay', 'fay hattı', 'fay hatları', 'kaf', 'daf', 'aktif fay', 'kuzey anadolu', 'doğu anadolu', 'ege graben')],
                'bildirim': responses[('bildirim', 'uyarı', 'whatsapp', 'mesaj', 'sms', 'alarm', 'nasıl bildirim alırım', 'bildirim ayarla')],
                'hasar': responses[('hasar', 'hasar tahmini', 'hasar analizi', 'yıkım', 'zarar', 'bina hasarı', 'yapı hasarı')],
                'yardım': responses[('yardım', 'help', 'nasıl kullanılır', 'kullanım', 'ne yapabilirsin', 'komutlar', 'özellikler', 'neler yapabilir')],
                'sistem': responses[('nasıl çalışır', 'sistem', 'yapay zeka', 'ml', 'makine öğrenmesi', 'algoritma', 'model', 'ai', 'yz')],
                'büyüklük': responses[('büyüklük', 'magnitude', 'richter', 'm', 'kaç şiddet', 'şiddet', 'ölçek')],
                'derinlik': responses[('derinlik', 'derin', 'sığ', 'yer kabuğu', 'odak derinliği')],
                'uyarı': responses[('erken uyarı', 'uyarı sistemi', 'önceden haber', 'tahmin', 'önceden bilmek')],
                'il': responses[('ankara', 'izmir', 'bursa', 'antalya', 'adana', 'gaziantep', 'konya', 'şehir', 'il', 'hangi il')],
                'anomali': responses[('anomali', 'olağandışı', 'normal değil', 'garip', 'anormal')],
                'harita': responses[('harita', 'görselleştirme', 'görsel', 'map', 'haritada')],
            }
            
            for pattern, response in similar_patterns.items():
                if pattern in message_lower:
                    response_text = response
                    break
        
        # Özel işlemler (veri seti, hava durumu, il bazlı deprem durumları)
        if needs_special_processing:
            if special_type == 'dataset_info':
                # Veri seti bilgilerini al
                try:
                    if not os.path.exists(EARTHQUAKE_HISTORY_FILE):
                        response_text = '📊 VERİ SETİ DURUMU:\n\n❌ Henüz veri seti oluşturulmamış.\n\n💡 Sistem otomatik olarak her 30 dakikada bir veri toplamaya başladığında burada görünecek.'
                    else:
                        file_size = os.path.getsize(EARTHQUAKE_HISTORY_FILE)
                        file_size_kb = round(file_size / 1024, 2)
                        
                        with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                            history = json.load(f)
                        
                        if not history or len(history) == 0:
                            response_text = '📊 VERİ SETİ DURUMU:\n\n⚠️ Veri seti boş.\n\n💡 Sistem otomatik olarak veri toplamaya devam ediyor.'
                        else:
                            total_records = len(history)
                            cities = set()
                            timestamps = []
                            risk_scores = []
                            
                            for record in history:
                                if 'city' in record:
                                    cities.add(record['city'])
                                if 'timestamp' in record:
                                    timestamps.append(record['timestamp'])
                                if 'risk_score' in record:
                                    risk_scores.append(record['risk_score'])
                            
                            date_range_text = ''
                            if timestamps:
                                min_timestamp = min(timestamps)
                                max_timestamp = max(timestamps)
                                min_date = datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M')
                                max_date = datetime.fromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M')
                                days_span = round((max_timestamp - min_timestamp) / 86400, 1)
                                date_range_text = f'\n📅 Tarih Aralığı: {min_date} - {max_date} ({days_span} gün)'
                            
                            last_update_text = ''
                            if timestamps:
                                last_timestamp = max(timestamps)
                                last_update = datetime.fromtimestamp(last_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                                last_update_text = f'\n🔄 Son Güncelleme: {last_update}'
                            
                            risk_stats_text = ''
                            if risk_scores:
                                risk_stats_text = f'\n📈 Risk Skoru: Min={min(risk_scores):.1f}, Max={max(risk_scores):.1f}, Ortalama={sum(risk_scores)/len(risk_scores):.1f}'
                            
                            model_status = '✅ Eğitilmiş' if os.path.exists(RISK_PREDICTION_MODEL_FILE) else '⚠️ Henüz eğitilmemiş'
                            
                            response_text = f'📊 EĞİTİM VERİ SETİ BİLGİLERİ:\n\n📊 Toplam Kayıt: {total_records:,}\n🏙️ Şehir Sayısı: {len(cities)}\n💾 Dosya Boyutu: {file_size_kb} KB{date_range_text}{last_update_text}{risk_stats_text}\n🤖 Model Durumu: {model_status}\n\n💡 Otomatik Eğitim: Model her 24 saatte bir veya veri seti 100, 500, 1000, 2000, 5000, 10000 kayıt eşiklerine ulaştığında otomatik olarak eğitilir.'
                except Exception as e:
                    response_text = f'❌ Veri seti bilgileri alınırken hata oluştu: {str(e)}'
            
            elif special_type == 'weather':
                # Hava durumu bilgileri - Gerçek zamanlı API entegrasyonu
                try:
                    # Mesajdan şehir adını çıkar
                    city_found = None
                    for city_name in TURKEY_CITIES.keys():
                        if city_name.lower() in message_lower:
                            city_found = city_name
                            break
                    
                    if city_found:
                        city_data = TURKEY_CITIES[city_found]
                        lat = city_data['lat']
                        lon = city_data['lon']
                        
                        # OpenWeatherMap API (ücretsiz tier)
                        # Not: API key environment variable'dan alınmalı
                        weather_api_key = os.environ.get('OPENWEATHER_API_KEY', '')
                        if weather_api_key:
                            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}&units=metric&lang=tr"
                            try:
                                weather_response = requests.get(weather_url, timeout=5)
                                if weather_response.status_code == 200:
                                    weather_data = weather_response.json()
                                    temp = weather_data['main']['temp']
                                    feels_like = weather_data['main']['feels_like']
                                    humidity = weather_data['main']['humidity']
                                    description = weather_data['weather'][0]['description'].title()
                                    wind_speed = weather_data.get('wind', {}).get('speed', 0)
                                    
                                    response_text = f'🌤️ {city_found.upper()} HAVA DURUMU (Güncel):\n\n'
                                    response_text += f'🌡️ Sıcaklık: {temp:.1f}°C (Hissedilen: {feels_like:.1f}°C)\n'
                                    response_text += f'☁️ Durum: {description}\n'
                                    response_text += f'💧 Nem: {humidity}%\n'
                                    response_text += f'💨 Rüzgar: {wind_speed:.1f} m/s\n\n'
                                    response_text += '⚠️ DEPREM İLE İLİŞKİSİ:\n'
                                    if 'yağmur' in description.lower() or 'rain' in description.lower():
                                        response_text += '• Yağmurlu hava deprem sonrası arama-kurtarma çalışmalarını zorlaştırabilir\n'
                                    if temp < 5:
                                        response_text += '• Soğuk hava acil durum çantanızda sıcak tutacak kıyafetler gerektirir\n'
                                    if wind_speed > 10:
                                        response_text += '• Güçlü rüzgar çadır kurulumunu zorlaştırabilir\n'
                                    response_text += '\n💡 Hava durumunu sürekli takip edin!'
                                else:
                                    raise Exception("API yanıt hatası")
                            except Exception as e:
                                print(f"[WEATHER API] Hata: {e}")
                                # Fallback
                                response_text = f'🌤️ {city_found.upper()} HAVA DURUMU:\n\n'
                                response_text += '📌 Güncel hava durumu için:\n'
                                response_text += '• Meteoroloji Genel Müdürlüğü: mgm.gov.tr\n'
                                response_text += '• Hava durumu uygulamaları\n'
                                response_text += f'• {city_found} için hava durumu takibi yapın\n\n'
                                response_text += '⚠️ Kötü hava koşulları deprem sonrası çalışmaları etkileyebilir!'
                        else:
                            # API key yok, genel bilgi
                            response_text = f'🌤️ {city_found.upper()} HAVA DURUMU:\n\n'
                            response_text += '📌 Güncel hava durumu için:\n'
                            response_text += '• Meteoroloji Genel Müdürlüğü: mgm.gov.tr\n'
                            response_text += '• Hava durumu uygulamaları\n'
                            response_text += f'• {city_found} için hava durumu takibi yapın\n\n'
                            response_text += '⚠️ ÖNEMLİ:\n'
                            response_text += '• Kötü hava koşulları deprem sonrası arama-kurtarma çalışmalarını zorlaştırabilir\n'
                            response_text += '• Acil durum çantanızda yağmurluk ve sıcak tutacak kıyafetler bulundurun\n'
                            response_text += '• Kış aylarında battaniye ve sıcak içecek önemlidir\n'
                            response_text += '\n💡 Deprem sonrası hava durumunu takip etmek hayati önem taşır!'
                    else:
                        # Genel hava durumu bilgisi
                        response_text = '🌤️ GÜNLÜK HAVA DURUMU BİLGİLERİ:\n\n'
                        response_text += '📌 Hava durumu bilgileri için:\n'
                        response_text += '• Meteoroloji Genel Müdürlüğü: mgm.gov.tr\n'
                        response_text += '• Hava durumu uygulamaları kullanabilirsiniz\n'
                        response_text += '• Radyo/TV hava durumu bültenlerini takip edin\n\n'
                        response_text += '💡 Belirli bir şehir için sorabilirsiniz (örn: "İstanbul hava durumu", "Konya hava nasıl")\n\n'
                        response_text += '⚠️ ÖNEMLİ:\n'
                        response_text += '• Kötü hava koşulları (şiddetli yağmur, kar, fırtına) deprem sonrası arama-kurtarma çalışmalarını zorlaştırabilir\n'
                        response_text += '• Acil durum çantanızda yağmurluk ve sıcak tutacak kıyafetler bulundurun\n'
                        response_text += '• Kış aylarında battaniye ve sıcak içecek önemlidir\n\n'
                        response_text += '💡 Deprem sonrası hava durumunu takip etmek hayati önem taşır!'
                except Exception as e:
                    response_text = f'❌ Hava durumu bilgisi alınırken hata oluştu: {str(e)}'
            
            elif special_type == 'city_earthquake_status':
                # İl bazlı deprem durumları - gerçek zamanlı veri
                try:
                    earthquakes = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=60)
                    if not earthquakes:
                        response_text = '⚠️ Şu anda deprem verileri alınamıyor. Lütfen daha sonra tekrar deneyin.'
                    else:
                        # Mesajdan şehir adını çıkar
                        city_found = None
                        for city_name in TURKEY_CITIES.keys():
                            if city_name.lower() in message_lower:
                                city_found = city_name
                                break
                        
                        if not city_found:
                            # Genel il bazlı bilgi
                            city_earthquakes = {}
                            for eq in earthquakes:
                                if eq.get('geojson') and eq['geojson'].get('coordinates'):
                                    lon, lat = eq['geojson']['coordinates']
                                    nearest_city, distance = find_nearest_city(lat, lon)
                                    if nearest_city not in city_earthquakes:
                                        city_earthquakes[nearest_city] = []
                                    city_earthquakes[nearest_city].append(eq)
                            
                            # En çok deprem olan şehirler
                            top_cities = sorted(city_earthquakes.items(), key=lambda x: len(x[1]), reverse=True)[:5]
                            
                            response_text = '🏙️ İL BAZINDA DEPREM DURUMLARI (Son 24 Saat):\n\n'
                            if top_cities:
                                for city, eqs in top_cities:
                                    max_mag = max([e.get('mag', 0) for e in eqs], default=0)
                                    response_text += f'📍 {city}: {len(eqs)} deprem (En büyük: M{max_mag:.1f})\n'
                            else:
                                response_text += 'Son 24 saatte kayda değer deprem aktivitesi görülmüyor.\n'
                            
                            response_text += '\n💡 Belirli bir şehir için sorabilirsiniz (örn: "İstanbul deprem durumu")'
                        else:
                            # Belirli şehir için detaylı bilgi
                            city_data = TURKEY_CITIES[city_found]
                            city_lat = city_data['lat']
                            city_lon = city_data['lon']
                            
                            # Şehre yakın depremler (150 km içinde)
                            nearby_earthquakes = []
                            for eq in earthquakes:
                                if eq.get('geojson') and eq['geojson'].get('coordinates'):
                                    lon, lat = eq['geojson']['coordinates']
                                    distance = haversine(city_lat, city_lon, lat, lon)
                                    if distance <= 150:
                                        nearby_earthquakes.append((eq, distance))
                            
                            # Risk analizi
                            risk_result = predict_earthquake_risk(earthquakes, city_lat, city_lon)
                            risk_score = risk_result.get('risk_score', 0)
                            
                            response_text = f'🏙️ {city_found.upper()} DEPREM DURUMU:\n\n'
                            response_text += f'📊 Risk Skoru: {risk_score:.1f}/10\n'
                            
                            if nearby_earthquakes:
                                nearby_earthquakes.sort(key=lambda x: x[0].get('mag', 0), reverse=True)
                                response_text += f'\n📍 Son 24 Saatte 150 km İçinde: {len(nearby_earthquakes)} deprem\n'
                                response_text += f'• En büyük: M{nearby_earthquakes[0][0].get("mag", 0):.1f} ({nearby_earthquakes[0][1]:.1f} km uzaklıkta)\n'
                            else:
                                response_text += '\n📍 Son 24 saatte 150 km içinde deprem görülmedi.\n'
                            
                            response_text += '\n💡 Detaylı analiz için "İl Bazında Risk Analizi" butonunu kullanabilirsiniz.'
                except Exception as e:
                    response_text = f'❌ İl bazlı deprem durumu alınırken hata oluştu: {str(e)}'
        
        # Gelişmiş akıllı yanıt sistemi
        if not response_text:
            # Sosyal medya analizi soruları (daha iyi pattern matching)
            if any(phrase in message_lower for phrase in ['sosyal medya', 'sosyal medya analizi', 'sosyal medya analizi yap', 'twitter', 'instagram', 'facebook', 'tweet', 'paylaşım', 'trend', 'gündem', 'sosyal medya analiz']):
                response_text = '📱 SOSYAL MEDYA ANALİZİ:\n\n'
                response_text += '🔍 Deprem ile ilgili sosyal medya analizi yapabilirim:\n\n'
                response_text += '📊 ANALİZ KONULARI:\n'
                response_text += '• Twitter/X\'te deprem gündemi ve trendler\n'
                response_text += '• Instagram\'da deprem paylaşımları ve etiketler\n'
                response_text += '• Facebook\'ta deprem grupları ve tartışmalar\n'
                response_text += '• Genel trend analizi\n'
                response_text += '• Gündem takibi\n\n'
                response_text += '💡 ÖRNEK SORULAR:\n'
                response_text += '• "Twitter\'da deprem gündemi ne?"\n'
                response_text += '• "Deprem ile ilgili son trendler"\n'
                response_text += '• "Sosyal medyada deprem konuşmaları"\n'
                response_text += '• "Instagram\'da deprem paylaşımları"\n\n'
                response_text += '⚠️ NOT: Gerçek zamanlı sosyal medya analizi için API entegrasyonu gereklidir.\n'
                response_text += 'Şu anda genel bilgi ve rehberlik sağlayabilirim.'
        
        if not response_text:
            # Ruh hali analizi soruları (daha iyi pattern - yukarıda korku zaten yakalandı)
            if any(phrase in message_lower for phrase in ['ruh hali', 'duygu', 'hissediyorum', 'nasıl hissediyorum', 'mood', 'duygusal', 'ruh halim', 'nasıl hissediyorum']):
                current_mood = context.get('user_mood', 'nötr')
                if current_mood == 'negatif':
                    response_text = '😔 Ruh halinizi anlıyorum. Deprem konusunda endişeli olmanız normal.\n\n'
                    response_text += '💚 ÖNERİLER:\n'
                    response_text += '• Hazırlık yapmak endişelerinizi azaltır\n'
                    response_text += '• Acil durum planı yapın\n'
                    response_text += '• Aile ile konuşun\n'
                    response_text += '• Profesyonel destek alın (gerekirse)\n'
                    response_text += '• Doğru bilgi kaynaklarından bilgi alın\n\n'
                    response_text += '🛡️ Hazırlık yapmak sizi güçlendirir!'
                elif current_mood == 'pozitif':
                    response_text = '😊 Pozitif yaklaşımınız harika! Hazırlıklı olmak önemli.\n\n'
                    response_text += '✅ Devam edin:\n'
                    response_text += '• Acil durum çantanızı hazırlayın\n'
                    response_text += '• Aile planınızı gözden geçirin\n'
                    response_text += '• Bilgilenmeye devam edin\n\n'
                    response_text += '💪 Hazırlık = Güvenlik!'
                else:
                    response_text = '🤔 Ruh halinizi analiz ediyorum...\n\n'
                    response_text += '💡 Deprem konusunda bilgilenmek ve hazırlık yapmak önemlidir.\n'
                    response_text += 'Size nasıl yardımcı olabilirim?'
        
        if not response_text:
            # Genel sohbet ve akıllı yanıtlar
            if any(word in message_lower for word in ['nasılsın', 'ne yapıyorsun', 'ne haber', 'naber', 'iyi misin']):
                response_text = '😊 İyiyim, teşekkürler! Size deprem güvenliği konusunda yardımcı olmak için buradayım.\n\n'
                response_text += 'Size nasıl yardımcı olabilirim?\n'
                response_text += '• 🔍 Risk analizi\n'
                response_text += '• 📊 Deprem bilgileri\n'
                response_text += '• 🛡️ Güvenlik önlemleri\n'
                response_text += '• 🌤️ Hava durumu\n'
                response_text += '• 📱 Sosyal medya analizi\n'
                response_text += '• 💭 Ruh hali analizi\n'
                response_text += '• Ve daha fazlası!'
        
        if not response_text:
            # Soru tiplerine göre akıllı yanıt
                question_words = ['nedir', 'nasıl', 'ne', 'nerede', 'kim', 'hangi', 'kaç', 'neden', 'niçin', 'ne zaman']
                has_question = any(qw in message_lower for qw in question_words)
                
                if has_question:
                    response_text = '🤔 Bu sorunuzu tam olarak anlayamadım. Şu konularda size yardımcı olabilirim:\n\n'
                    response_text += '• 🔍 Risk analizi ve tahmini nasıl yapılır?\n'
                    response_text += '• 📊 Son depremler nerede görüntülenir?\n'
                    response_text += '• 🛡️ Deprem sırasında ne yapmalıyım?\n'
                    response_text += '• 🏛️ İstanbul erken uyarı sistemi nasıl çalışır?\n'
                    response_text += '• 📱 WhatsApp bildirimleri nasıl ayarlanır?\n'
                    response_text += '• 🗺️ Fay hatları nerede?\n'
                    response_text += '• 🤖 Sistem nasıl çalışır?\n'
                    response_text += '• 🌤️ Hava durumu bilgileri\n'
                    response_text += '• 📱 Sosyal medya analizi\n'
                    response_text += '• 💭 Ruh hali analizi\n\n'
                    response_text += 'Lütfen daha spesifik bir soru sorun!'
                else:
                    # Context-aware yanıt
                    if context['history']:
                        last_topic = context['history'][-1].get('user', '')
                        if 'deprem' in last_topic.lower():
                            response_text = '💬 Deprem konusunda devam edelim. Size nasıl yardımcı olabilirim?\n\n'
                            response_text += '• Son depremler hakkında bilgi\n'
                            response_text += '• Risk analizi\n'
                            response_text += '• Güvenlik önlemleri\n'
                            response_text += '• Erken uyarı sistemi'
                        else:
                            response_text = '🤔 Anladım, ancak bu konuda daha fazla bilgi veremiyorum.\n\n'
                            response_text += 'Size şunlar hakkında yardımcı olabilirim:\n\n'
                            response_text += '• 🔍 Risk analizi ve tahmini\n'
                            response_text += '• 📊 Deprem bilgileri ve haritalar\n'
                            response_text += '• 🛡️ Güvenlik önlemleri\n'
                            response_text += '• 🏛️ İstanbul erken uyarı sistemi\n'
                            response_text += '• 📱 WhatsApp bildirimleri\n'
                            response_text += '• 🗺️ Fay hatları\n'
                            response_text += '• 🤖 Makine öğrenmesi ve sistem\n'
                            response_text += '• 📏 Deprem büyüklüğü ve derinlik\n'
                            response_text += '• 🏙️ İl bazında analiz\n'
                            response_text += '• 🌤️ Hava durumu\n'
                            response_text += '• 📱 Sosyal medya analizi\n'
                            response_text += '• 💭 Ruh hali analizi\n\n'
                            response_text += 'Lütfen bu konulardan birini sorun!'
                    else:
                        response_text = '🤔 Anladım, ancak bu konuda daha fazla bilgi veremiyorum.\n\n'
                        response_text += 'Size şunlar hakkında yardımcı olabilirim:\n\n'
                        response_text += '• 🔍 Risk analizi ve tahmini\n'
                        response_text += '• 📊 Deprem bilgileri ve haritalar\n'
                        response_text += '• 🛡️ Güvenlik önlemleri\n'
                        response_text += '• 🏛️ İstanbul erken uyarı sistemi\n'
                        response_text += '• 📱 WhatsApp bildirimleri\n'
                        response_text += '• 🗺️ Fay hatları\n'
                        response_text += '• 🤖 Makine öğrenmesi ve sistem\n'
                        response_text += '• 📏 Deprem büyüklüğü ve derinlik\n'
                        response_text += '• 🏙️ İl bazında analiz\n'
                        response_text += '• 🌤️ Hava durumu\n'
                        response_text += '• 📱 Sosyal medya analizi\n'
                        response_text += '• 💭 Ruh hali analizi\n\n'
                        response_text += 'Lütfen bu konulardan birini sorun!'
        
        # Ruh haline göre yanıtı özelleştir
        if context.get('user_mood') == 'negatif' and '😔' not in response_text:
            response_text = '💚 ' + response_text
        
        # Konuşma geçmişine yanıtı ekle
        context['history'].append({
            'bot': response_text,
            'timestamp': time.time()
        })
        
        # Son güncelleme zamanı
        context['last_interaction'] = time.time()
        
        return jsonify({
            "response": response_text,
            "mood": context.get('user_mood', 'nötr'),
            "session_id": session_id
        })
        
    except Exception as e:
        print(f"[ERROR] Chatbot hatası: {e}")
        return jsonify({"response": "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."}), 500

@app.route('/api/test-meta-token', methods=['GET'])
def test_meta_token():
    """
    Meta WhatsApp token'ını test eder.
    ChatGPT önerisi: https://graph.facebook.com/v22.0/833412653196098?access_token=TOKEN
    """
    if not META_WHATSAPP_ACCESS_TOKEN:
        return jsonify({
            "success": False,
            "message": "Token bulunamadı. META_WA_TOKEN environment variable'ı ekleyin."
        }), 400
    
    try:
        test_url = f"https://graph.facebook.com/{META_WHATSAPP_API_VERSION}/{META_WHATSAPP_PHONE_NUMBER_ID}?access_token={META_WHATSAPP_ACCESS_TOKEN}"
        response = requests.get(test_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "success": True,
                "message": "✅ Token çalışıyor!",
                "phone_number_id": data.get('id'),
                "verified_name": data.get('verified_name', 'N/A'),
                "display_phone_number": data.get('display_phone_number', 'N/A')
            })
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
            return jsonify({
                "success": False,
                "message": f"❌ Token hatası: {error_msg}",
                "status_code": response.status_code
            }), response.status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Test hatası: {str(e)}"
        }), 500

@app.route('/api/test-meta-whatsapp-send', methods=['POST'])
def test_meta_whatsapp_send():
    """
    Meta WhatsApp ile test mesajı gönderir (ChatGPT önerisi).
    Sadece session açılmışsa çalışır.
    """
    if not USE_META_WHATSAPP:
        return jsonify({
            "success": False,
            "message": "Meta WhatsApp API ayarları yapılmamış"
        }), 503
    
    data = request.get_json() or {}
    test_number = data.get('to', '905468964210')  # Varsayılan test numarası
    
    test_message = "🚨 Test başarılı. AfetBot aktif."
    
    success, error = send_whatsapp_via_meta_api(test_number, test_message)
    
    if success:
        return jsonify({
            "success": True,
            "message": "✅ Test mesajı gönderildi!",
            "to": test_number
        })
    else:
        return jsonify({
            "success": False,
            "message": f"❌ Mesaj gönderilemedi: {error}",
            "error": error,
            "note": "Session açılmamış olabilir. Önce opt-in linki ile session açın."
        }), 400

@app.route('/api/get-opt-in-link', methods=['GET'])
def get_opt_in_link():
    """
    Meta WhatsApp için opt-in linki döndürür.
    Kullanıcı bu linke tıklayıp 'basla' yazarsa 24 saat boyunca serbest metin gönderebiliriz.
    """
    if not USE_META_WHATSAPP:
        return jsonify({
            "success": False,
            "message": "Meta WhatsApp API ayarları yapılmamış"
        }), 503
    
    # Opt-in linki oluştur (wa.me formatında)
    # Test numarası: +15551679784 -> 15551679784
    test_number_clean = META_WHATSAPP_TEST_NUMBER.replace('+', '').replace(' ', '').replace('-', '')
    opt_in_link = f"https://wa.me/{test_number_clean}?text=basla"
    
    return jsonify({
        "success": True,
        "opt_in_link": opt_in_link,
        "test_number": META_WHATSAPP_TEST_NUMBER,
        "message": "Bu linke tıklayıp 'basla' yazın. Sonra 24 saat boyunca serbest metin bildirimleri alabilirsiniz.",
        "instructions": [
            "1. Aşağıdaki linke tıklayın",
            "2. WhatsApp'ta 'basla' yazın ve gönderin",
            "3. Artık 24 saat boyunca serbest metin bildirimleri alabilirsiniz"
        ]
    })

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

# WhatsApp Web servisi kaldırıldı - sadece Twilio kullanılıyor

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
    
    # Otomatik model eğitimi için takip değişkenleri
    last_training_time = 0  # Son eğitim zamanı
    training_thresholds = [100, 500, 1000, 2000, 5000, 10000]  # Veri seti büyüklüğü eşikleri
    last_training_data_size = 0  # Son eğitimdeki veri seti büyüklüğü
    
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
            
            print(f"[VERI TOPLAMA] Kandilli'den {len(earthquakes)} deprem verisi çekildi.")
            
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
            seen_earthquake_ids = set()  # Kandilli deprem verileri için
            
            for record in existing_data:
                if 'features' in record:
                    # Şehir bazlı kayıtlar için
                    city = record.get('city', '')
                    lat = record.get('lat', 0)
                    lon = record.get('lon', 0)
                    timestamp = record.get('timestamp', 0)
                    record_id = f"{city}_{lat:.4f}_{lon:.4f}_{timestamp:.0f}"
                    seen_ids.add(record_id)
                elif 'geojson' in record:
                    # Kandilli ham deprem verisi için
                    if record.get('geojson') and record['geojson'].get('coordinates'):
                        lon, lat = record['geojson']['coordinates']
                        eq_id = f"{record.get('mag', 0)}_{lat:.4f}_{lon:.4f}_{record.get('date', '')}_{record.get('time', '')}"
                        seen_earthquake_ids.add(eq_id)
            
            # Yeni Kandilli deprem verilerini ekle (ham veri olarak)
            new_earthquake_data = []
            for eq in earthquakes:
                if eq.get('geojson') and eq['geojson'].get('coordinates'):
                    lon, lat = eq['geojson']['coordinates']
                    eq_id = f"{eq.get('mag', 0)}_{lat:.4f}_{lon:.4f}_{eq.get('date', '')}_{eq.get('time', '')}"
                    if eq_id not in seen_earthquake_ids:
                        seen_earthquake_ids.add(eq_id)
                        # Ham deprem verisini ekle (eğitim için)
                        eq_record = eq.copy()
                        eq_record['source'] = 'kandilli'
                        eq_record['collected_at'] = time.time()
                        new_earthquake_data.append(eq_record)
            
            if new_earthquake_data:
                print(f"[VERI TOPLAMA] {len(new_earthquake_data)} yeni Kandilli deprem verisi eğitime eklendi.")
            
            # Yeni eğitim verisi oluştur (tüm şehirler için)
            new_training_data = []
            cities_processed = 0
            
            # Tüm 81 il için veri oluştur
            for city_name, city_data in TURKEY_CITIES.items():
                city_lat = city_data['lat']
                city_lon = city_data['lon']
                
                # Özellik çıkar (Kandilli verileri ile)
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
                            'timestamp': current_time,
                            'earthquake_count': len(earthquakes)  # Kandilli'den çekilen toplam deprem sayısı
                        })
                        cities_processed += 1
            
            # Yeni verileri mevcut veriye ekle
            data_updated = False
            
            # Önce Kandilli ham deprem verilerini ekle
            if new_earthquake_data:
                existing_data.extend(new_earthquake_data)
                data_updated = True
                print(f"[VERI TOPLAMA] ✅ {len(new_earthquake_data)} yeni Kandilli ham deprem verisi eğitim veri setine eklendi.")
            
            # Sonra şehir bazlı eğitim verilerini ekle
            if new_training_data:
                existing_data.extend(new_training_data)
                data_updated = True
                print(f"[VERI TOPLAMA] ✅ {cities_processed} şehir için {len(new_training_data)} yeni eğitim verisi eklendi.")
            
            # Veriyi kaydet (hem Kandilli hem şehir bazlı veriler varsa)
            if data_updated:
                # Son 50,000 kaydı tut (Kandilli verileri de dahil olduğu için limit artırıldı)
                if len(existing_data) > 50000:
                    existing_data = existing_data[-50000:]
                    print(f"[VERI TOPLAMA] Veri seti 50,000 kayıtla sınırlandırıldı (en eski kayıtlar silindi).")
                
                try:
                    with open(EARTHQUAKE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, ensure_ascii=False, indent=2)
                    
                    # Veri seti istatistikleri
                    city_count = sum(1 for r in existing_data if 'features' in r)
                    kandilli_count = sum(1 for r in existing_data if r.get('source') == 'kandilli')
                    print(f"[VERI TOPLAMA] 📊 Toplam: {len(existing_data)} kayıt ({city_count} şehir bazlı, {kandilli_count} Kandilli ham veri)")
                    
                    # OTOMATIK MODEL EĞİTİMİ KONTROLÜ
                    current_time = time.time()
                    current_data_size = len(existing_data)
                    should_train = False
                    training_reason = ""
                    
                    # 1. Zaman bazlı kontrol: Her 24 saatte bir eğitim
                    if last_training_time == 0 or (current_time - last_training_time) >= 86400:  # 24 saat = 86400 saniye
                        should_train = True
                        training_reason = "24 saatlik periyot doldu"
                    
                    # 2. Veri seti büyüklüğü kontrolü: Belirli eşiklere ulaştığında eğitim
                    elif current_data_size >= 50:  # Minimum eğitim için 50 kayıt gerekli
                        for threshold in training_thresholds:
                            if last_training_data_size < threshold <= current_data_size:
                                should_train = True
                                training_reason = f"Veri seti {threshold} kayıt eşiğine ulaştı (önceki: {last_training_data_size}, şimdi: {current_data_size})"
                                break
                    
                    # Model eğitimi yap
                    if should_train:
                        print(f"\n[OTOMATIK EGITIM] Model eğitimi başlatılıyor... ({training_reason})")
                        try:
                            models = train_risk_prediction_model(existing_data)
                            if models:
                                last_training_time = current_time
                                last_training_data_size = current_data_size
                                print(f"[OTOMATIK EGITIM] ✅ Model başarıyla eğitildi! ({len(models)} model)")
                                print(f"[OTOMATIK EGITIM] Eğitilen modeller: {list(models.keys())}")
                            else:
                                print(f"[OTOMATIK EGITIM] ⚠️ Model eğitilemedi (yeterli veri yok veya hata)")
                        except Exception as e:
                            print(f"[OTOMATIK EGITIM] ❌ Model eğitimi hatası: {e}")
                            import traceback
                            traceback.print_exc()
                    
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

# 2. Sürekli veri toplama (30 dakikada bir) + Otomatik model eğitimi
data_collection_thread = Thread(target=collect_training_data_continuously)
data_collection_thread.daemon = True
data_collection_thread.start()
print("[SISTEM] Sürekli veri toplama sistemi başlatıldı (her 30 dakikada bir).")
print("[SISTEM] Otomatik model eğitimi aktif:")
print("  - Her 24 saatte bir otomatik eğitim")
print("  - Veri seti 100, 500, 1000, 2000, 5000, 10000 kayıt eşiklerine ulaştığında otomatik eğitim")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Flask Sunucusu Başlatıldı: http://127.0.0.1:{port}/api/risk")
    app.run(host='0.0.0.0', port=port)