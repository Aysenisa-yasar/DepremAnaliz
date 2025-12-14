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
import requests.exceptions
import pandas as pd 

# --- FLASK UYGULAMASI VE AYARLARI ---
app = Flask(__name__)
CORS(app) 

# Kandilli verilerini çeken üçüncü taraf API
KANDILLI_API = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'

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
    """ Twilio üzerinden WhatsApp mesajı gönderir. Konum linki eklenebilir. """
    # Twilio bilgileri kontrolü
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        print("[WARNING] Twilio ayarlari yapilmamis! Ortam degiskenlerini kontrol edin.")
        print("  Gerekli: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER")
        return False
    
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
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] WhatsApp mesaji gonderilemedi: {error_msg}")
        
        # Hata mesajlarına göre öneriler
        if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
            print("[NOT] Twilio hesap bilgileri hatali olabilir. Kontrol edin:")
            print("  - Account SID dogru mu?")
            print("  - Auth Token dogru mu?")
            print("  - WhatsApp numarasi dogru formatta mi? (whatsapp:+14155238886)")
        elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
            print("[NOT] Twilio hesabinizda yetki sorunu var.")
            print("  - Hesabiniz aktif mi?")
            print("  - WhatsApp Sandbox'a katildiniz mi?")
        elif "not a valid" in error_msg.lower() or "format" in error_msg.lower():
            print("[NOT] Telefon numarasi format hatasi.")
            print("  - Numara ulke kodu ile baslamali (ornek: +905551234567)")
            print("  - WhatsApp Sandbox'a kayitli numara olmali")
        
        return False

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
    
    if len(recent_eqs) == 0:
        return None
    
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
    # Özellik çıkarımı
    features = extract_features(earthquakes, target_lat, target_lon)
    
    if features is None:
        return {"risk_level": "Düşük", "risk_score": 2.0, "method": "fallback", "reason": "Yeterli veri yok"}
    
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
            return {"risk_level": "Düşük", "risk_score": 2.0, "method": "fallback", "reason": "Model eğitilmemiş"}
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
    """
    if not earthquakes or len(earthquakes) < 5:
        return {"risk_level": "Düşük", "risk_score": 2.0, "reason": "Yeterli veri yok"}
    
    # Son 24 saatteki depremleri filtrele
    recent_earthquakes = []
    current_time = time.time()
    
    for eq in earthquakes:
        if eq.get('geojson') and eq['geojson'].get('coordinates'):
            lon, lat = eq['geojson']['coordinates']
            mag = eq.get('mag', 0)
            distance = haversine(target_lat, target_lon, lat, lon)
            
            # 200 km içindeki depremleri al
            if distance < 200 and mag >= 3.0:
                recent_earthquakes.append({
                    'mag': mag,
                    'distance': distance,
                    'lat': lat,
                    'lon': lon
                })
    
    if not recent_earthquakes:
        return {"risk_level": "Düşük", "risk_score": 2.0, "reason": "Yakın bölgede aktivite yok"}
    
    # Risk faktörleri
    avg_magnitude = np.mean([eq['mag'] for eq in recent_earthquakes])
    max_magnitude = max([eq['mag'] for eq in recent_earthquakes])
    count = len(recent_earthquakes)
    avg_distance = np.mean([eq['distance'] for eq in recent_earthquakes])
    
    # Yakın fay hattı kontrolü
    nearest_fault_distance = float('inf')
    for fault in TURKEY_FAULT_LINES:
        for coord in fault['coords']:
            fault_lat, fault_lon = coord
            dist = haversine(target_lat, target_lon, fault_lat, fault_lon)
            nearest_fault_distance = min(nearest_fault_distance, dist)
    
    # Risk skoru hesaplama (0-10 arası)
    risk_score = 0
    
    # Büyüklük faktörü
    risk_score += min(3.0, max_magnitude * 0.4)
    
    # Aktivite yoğunluğu
    risk_score += min(2.0, count * 0.2)
    
    # Mesafe faktörü (yakın depremler daha riskli)
    risk_score += min(2.0, max(0, (200 - avg_distance) / 100))
    
    # Fay hattı yakınlığı
    if nearest_fault_distance < 50:
        risk_score += 2.0
    elif nearest_fault_distance < 100:
        risk_score += 1.0
    
    risk_score = min(10.0, risk_score)
    
    # Risk seviyesi belirleme
    if risk_score >= 7.0:
        level = "Çok Yüksek"
    elif risk_score >= 5.0:
        level = "Yüksek"
    elif risk_score >= 3.0:
        level = "Orta"
    else:
        level = "Düşük"
    
    return {
        "risk_level": level,
        "risk_score": round(risk_score, 1),
        "factors": {
            "max_magnitude": round(max_magnitude, 1),
            "recent_count": count,
            "avg_distance": round(avg_distance, 1),
            "nearest_fault_km": round(nearest_fault_distance, 1)
        },
        "reason": f"Son 24 saatte {count} deprem, en büyük M{max_magnitude:.1f}"
    }


# --- API UÇ NOKTALARI ---

@app.route('/api/risk', methods=['GET'])
def get_risk_analysis():
    """ Ön uçtan gelen isteklere YZ analiz sonuçlarını döndürür. """
    
    print("Risk analizi isteği alındı...")
    start_time = time.time()
    
    try:
        response = requests.get(KANDILLI_API, timeout=10)
        response.raise_for_status() 
        earthquake_data = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        print(f"HATA: Kandilli verisi çekilemedi: {e}")
        return jsonify({"error": f"Veri kaynağına erişilemedi. {e}"}), 500

    risk_data = calculate_clustering_risk(earthquake_data)
    risk_data['fault_lines'] = TURKEY_FAULT_LINES
    risk_data['recent_earthquakes'] = earthquake_data[:20]  # Son 20 deprem
    
    end_time = time.time()
    print(f"Analiz süresi: {end_time - start_time:.2f} saniye")
    
    return jsonify(risk_data)

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
    data = request.get_json()
    lat = float(data.get('lat'))
    lon = float(data.get('lon'))
    use_ml = data.get('use_ml', True)  # ML kullanımı (varsayılan: True)
    
    try:
        earthquake_data = fetch_earthquake_data_with_retry(max_retries=3, timeout=30)
    except Exception as e:
        return jsonify({"error": f"Veri kaynağına erişilemedi. {e}"}), 500
    
    # Gelişmiş ML modeli ile tahmin
    if use_ml:
        prediction = predict_risk_with_ml(earthquake_data, lat, lon)
        # Anomali tespiti ekle
        anomaly = detect_anomalies(earthquake_data, lat, lon)
        prediction['anomaly'] = anomaly
    else:
        # Eski yöntem (fallback)
        prediction = predict_earthquake_risk(earthquake_data, lat, lon)
        prediction['method'] = 'traditional'
    
    return jsonify(prediction)

@app.route('/api/istanbul-early-warning', methods=['GET'])
def istanbul_early_warning():
    """ İstanbul için özel erken uyarı sistemi. """
    try:
        response = requests.get(KANDILLI_API, timeout=10)
        response.raise_for_status() 
        earthquake_data = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Veri kaynağına erişilemedi. {e}"}), 500
    
    warning = istanbul_early_warning_system(earthquake_data)
    return jsonify(warning)

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
    data = request.get_json()
    lat = float(data.get('lat'))
    lon = float(data.get('lon'))
    
    try:
        response = requests.get(KANDILLI_API, timeout=10)
        response.raise_for_status() 
        earthquake_data = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Veri kaynağına erişilemedi. {e}"}), 500
    
    anomaly = detect_anomalies(earthquake_data, lat, lon)
    return jsonify(anomaly)

@app.route('/api/fault-lines', methods=['GET'])
def get_fault_lines():
    """ Türkiye'nin aktif fay hatlarını döndürür. """
    return jsonify({"fault_lines": TURKEY_FAULT_LINES})

@app.route('/api/city-damage-analysis', methods=['GET'])
def city_damage_analysis():
    """ 5+ depremler için il bazında otomatik yapay zeka destekli hasar tahmini yapar. """
    try:
        response = requests.get(KANDILLI_API, timeout=10)
        response.raise_for_status() 
        earthquake_data = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Veri kaynağına erişilemedi. {e}"}), 500
    
    # 5+ depremleri filtrele
    major_earthquakes = [eq for eq in earthquake_data if eq.get('mag', 0) >= 5.0]
    
    if not major_earthquakes:
        return jsonify({
            "status": "no_major_earthquakes",
            "message": "Son 24 saatte 5.0 ve üzeri deprem tespit edilmedi.",
            "city_damages": []
        })
    
    city_damages = {}
    
    # Her büyük deprem için
    for eq in major_earthquakes:
        if not eq.get('geojson') or not eq['geojson'].get('coordinates'):
            continue
            
        lon_eq, lat_eq = eq['geojson']['coordinates']
        magnitude = eq.get('mag', 0)
        depth = eq.get('depth', 10)
        
        # Her il için mesafe ve hasar tahmini yap
        for city_name, city_data in TURKEY_CITIES.items():
            city_lat = city_data['lat']
            city_lon = city_data['lon']
            distance = haversine(lat_eq, lon_eq, city_lat, city_lon)
            
            # 300 km içindeki illeri analiz et
            if distance <= 300:
                building_structure = city_data['building_structure']
                
                # Yapay zeka destekli hasar tahmini
                damage_info = ai_damage_estimate(magnitude, depth, distance, building_structure)
                
                # İl için en yüksek hasar skorunu tut
                if city_name not in city_damages:
                    city_damages[city_name] = {
                        "city": city_name,
                        "lat": city_lat,
                        "lon": city_lon,
                        "max_damage_score": 0,
                        "damage_level": "Minimal",
                        "earthquakes_affecting": [],
                        "building_structure": building_structure
                    }
                
                if damage_info['damage_score'] > city_damages[city_name]['max_damage_score']:
                    city_damages[city_name]['max_damage_score'] = damage_info['damage_score']
                    city_damages[city_name]['damage_level'] = damage_info['level']
                    city_damages[city_name]['description'] = damage_info['description']
                    city_damages[city_name]['affected_buildings'] = damage_info['affected_buildings_percent']
                
                # Etkilenen deprem bilgilerini ekle
                city_damages[city_name]['earthquakes_affecting'].append({
                    "magnitude": magnitude,
                    "distance": round(distance, 1),
                    "depth": depth,
                    "location": eq.get('location', 'Bilinmiyor'),
                    "date": eq.get('date', ''),
                    "time": eq.get('time', '')
                })
    
    # Sıralama: En yüksek hasar skoruna göre
    sorted_cities = sorted(
        city_damages.values(),
        key=lambda x: x['max_damage_score'],
        reverse=True
    )
    
    return jsonify({
        "status": "success",
        "total_major_earthquakes": len(major_earthquakes),
        "affected_cities": len(sorted_cities),
        "city_damages": sorted_cities
    })

@app.route('/api/set-alert', methods=['POST'])
def set_alert_settings():
    """ Kullanıcının konumunu ve bildirim telefon numarasını kaydeder ve onay mesajı gönderir. """
    global user_alerts
    data = request.get_json()
    lat = float(data.get('lat'))
    lon = float(data.get('lon'))
    number = data.get('number') 
    
    if not lat or not lon or not number:
        return jsonify({"status": "error", "message": "Eksik konum veya telefon numarası bilgisi."}), 400
    
    if not number.startswith('+'):
        return jsonify({"status": "error", "message": "Telefon numarası ülke kodu ile (+XX) başlamalıdır."}), 400
    
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
    
    send_whatsapp_notification(number, confirmation_body, location_url)
    
    return jsonify({"status": "success", "message": "Bildirim ayarlarınız kaydedildi."})


# --- ARKA PLAN BİLDİRİM KONTROLÜ ---

def check_for_big_earthquakes():
    """ Arka planda sürekli çalışır, M >= 5.0 deprem olup olmadığını kontrol eder. """
    global last_big_earthquake, user_alerts
    
    while True:
        time.sleep(60) 

        try:
            response = requests.get(KANDILLI_API, timeout=5)
            response.raise_for_status() 
            earthquakes = response.json().get('result', [])
        except requests.exceptions.RequestException:
            continue
        
        # İstanbul erken uyarı kontrolü
        istanbul_warning = istanbul_early_warning_system(earthquakes)
        if istanbul_warning['alert_level'] in ['KRİTİK', 'YÜKSEK']:
            print(f"🚨 İSTANBUL ERKEN UYARI: {istanbul_warning['alert_level']} - {istanbul_warning['message']}")
            # İstanbul için kayıtlı kullanıcılara bildirim gönder
            for number, coords in user_alerts.items():
                city, _ = find_nearest_city(coords['lat'], coords['lon'])
                if city == 'İstanbul':
                    body = f"🚨 İSTANBUL ERKEN UYARI SİSTEMİ 🚨\n"
                    body += f"Uyarı Seviyesi: {istanbul_warning['alert_level']}\n"
                    body += f"Uyarı Skoru: {istanbul_warning['alert_score']}/1.0\n"
                    body += f"Mesaj: {istanbul_warning['message']}\n"
                    if istanbul_warning.get('time_to_event'):
                        body += f"Tahmini Süre: {istanbul_warning['time_to_event']}\n"
                    body += f"\n⚠️ Lütfen hazırlıklı olun ve acil durum planınızı gözden geçirin!"
                    send_whatsapp_notification(number, body)

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
                            
                            send_whatsapp_notification(number, body)

# Arka plan iş parçacığını başlat
alert_thread = Thread(target=check_for_big_earthquakes)
alert_thread.daemon = True 
alert_thread.start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Flask Sunucusu Başlatıldı: http://127.0.0.1:{port}/api/risk")
    app.run(host='0.0.0.0', port=port)