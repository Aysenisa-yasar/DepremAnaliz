#!/usr/bin/env python3
# Türkiye'deki TÜM Kayıtlı Depremleri Toplama Scripti
# Büyük veri seti oluşturmak için

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    KANDILLI_API, TURKEY_CITIES, ISTANBUL_COORDS,
    EARTHQUAKE_HISTORY_FILE, extract_features, predict_earthquake_risk
)
import requests
import json
import time
from datetime import datetime, timedelta
import numpy as np

def fetch_earthquake_data_with_retry(url, max_retries=3, timeout=30):
    """API'den veri çeker, retry mekanizması ile."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            })
            response.raise_for_status()
            return response.json().get('result', [])
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"API timeout, {wait_time} saniye bekleyip tekrar deneniyor... (Deneme {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print("API timeout: Tüm denemeler başarısız")
                return []
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"API hatası: {e}, {wait_time} saniye bekleyip tekrar deneniyor...")
                time.sleep(wait_time)
                continue
            else:
                print(f"API hatası: Tüm denemeler başarısız - {e}")
                return []
    return []

def collect_all_historical_earthquakes():
    """Türkiye'deki tüm kayıtlı depremleri toplar."""
    print("="*60)
    print("TURKIYE'DEKI TUM KAYITLI DEPREMLERI TOPLAMA")
    print("="*60)
    
    all_earthquakes = []
    seen_ids = set()
    
    # 1. Kandilli canlı veriler (son 500 deprem)
    print("\n[1/4] Kandilli canli veriler toplaniyor...")
    for i in range(10):  # 10 kez çek (farklı zamanlarda)
        try:
            earthquakes = fetch_earthquake_data_with_retry(KANDILLI_API, max_retries=2, timeout=20)
            if earthquakes:
                for eq in earthquakes:
                    if eq.get('geojson') and eq['geojson'].get('coordinates'):
                        lon, lat = eq['geojson']['coordinates']
                        eq_id = f"{eq.get('mag', 0)}_{lat:.4f}_{lon:.4f}_{eq.get('date', '')}_{eq.get('time', '')}"
                        if eq_id not in seen_ids:
                            seen_ids.add(eq_id)
                            eq['timestamp'] = time.time()
                            all_earthquakes.append(eq)
                print(f"  [OK] {len(earthquakes)} deprem verisi eklendi (Toplam: {len(all_earthquakes)})")
            time.sleep(2)  # API'ye yük bindirmemek için
        except Exception as e:
            print(f"  [HATA] {e}")
    
    # 2. Kandilli tarihsel veriler (son 1 ay - farklı tarihler)
    print("\n[2/4] Kandilli tarihsel veriler toplaniyor...")
    historical_urls = [
        'https://api.orhanaydogdu.com.tr/deprem/kandilli/archive',
        'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'
    ]
    
    for url in historical_urls:
        try:
            earthquakes = fetch_earthquake_data_with_retry(url, max_retries=2, timeout=20)
            if earthquakes:
                for eq in earthquakes:
                    if eq.get('geojson') and eq['geojson'].get('coordinates'):
                        lon, lat = eq['geojson']['coordinates']
                        eq_id = f"{eq.get('mag', 0)}_{lat:.4f}_{lon:.4f}_{eq.get('date', '')}_{eq.get('time', '')}"
                        if eq_id not in seen_ids:
                            seen_ids.add(eq_id)
                            if 'timestamp' not in eq:
                                eq['timestamp'] = time.time()
                            all_earthquakes.append(eq)
                print(f"  [OK] {len(earthquakes)} tarihsel deprem verisi eklendi (Toplam: {len(all_earthquakes)})")
        except Exception as e:
            print(f"  [HATA] {e}")
    
    # 3. Mevcut tarihsel veriyi yükle ve birleştir
    print("\n[3/4] Mevcut tarihsel veri yukleniyor...")
    if os.path.exists(EARTHQUAKE_HISTORY_FILE):
        try:
            with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            for eq in existing_data:
                if eq.get('geojson') and eq['geojson'].get('coordinates'):
                    lon, lat = eq['geojson']['coordinates']
                    eq_id = f"{eq.get('mag', 0)}_{lat:.4f}_{lon:.4f}_{eq.get('date', '')}_{eq.get('time', '')}"
                    if eq_id not in seen_ids:
                        seen_ids.add(eq_id)
                        all_earthquakes.append(eq)
            
            print(f"  [OK] {len(existing_data)} mevcut veri eklendi (Toplam: {len(all_earthquakes)})")
        except Exception as e:
            print(f"  [HATA] Mevcut veri yuklenemedi: {e}")
    
    # 4. Türkiye'deki tüm şehirler için eğitim verisi oluştur
    print("\n[4/4] Tum sehirler icin egitim verisi olusturuluyor...")
    training_data = []
    
    # Tüm 81 il için veri oluştur
    for city_name, city_data in TURKEY_CITIES.items():
        lat = city_data['lat']
        lon = city_data['lon']
        
        # Özellik çıkar
        features = extract_features(all_earthquakes, lat, lon, time_window_hours=48)
        if features:
            # Risk skoru hesapla
            risk_result = predict_earthquake_risk(all_earthquakes, lat, lon)
            risk_score = risk_result.get('risk_score', 2.0)
            
            training_data.append({
                'city': city_name,
                'lat': lat,
                'lon': lon,
                'features': features,
                'risk_score': risk_score,
                'timestamp': time.time(),
                'earthquake_count': len(all_earthquakes)
            })
    
    print(f"  [OK] {len(training_data)} sehir icin egitim verisi olusturuldu")
    
    # 5. Veriyi kaydet
    print("\n[5/5] Veri kaydediliyor...")
    try:
        # Tüm deprem verilerini kaydet
        with open(EARTHQUAKE_HISTORY_FILE.replace('.json', '_all_earthquakes.json'), 'w', encoding='utf-8') as f:
            json.dump(all_earthquakes, f, ensure_ascii=False, indent=2)
        print(f"  [OK] {len(all_earthquakes)} deprem verisi kaydedildi")
        
        # Eğitim verilerini kaydet
        if os.path.exists(EARTHQUAKE_HISTORY_FILE):
            with open(EARTHQUAKE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing_training = json.load(f)
            training_data.extend(existing_training)
        
        # Son 50000 örneği tut (hafıza için)
        if len(training_data) > 50000:
            training_data = training_data[-50000:]
        
        with open(EARTHQUAKE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] {len(training_data)} egitim ornegi kaydedildi")
        
        print("\n" + "="*60)
        print("[BASARILI] TUM VERILER TOPLANDI VE KAYDEDILDI!")
        print("="*60)
        print(f"Toplam Deprem Verisi: {len(all_earthquakes)}")
        print(f"Toplam Egitim Ornegi: {len(training_data)}")
        print(f"Veri Seti Dosyasi: {EARTHQUAKE_HISTORY_FILE}")
        print("="*60)
        
        return all_earthquakes, training_data
    except Exception as e:
        print(f"  [HATA] Veri kaydedilemedi: {e}")
        return [], []

if __name__ == "__main__":
    collect_all_historical_earthquakes()

