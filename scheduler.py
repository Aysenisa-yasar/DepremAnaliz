#!/usr/bin/env python3
"""
scheduler.py
Otomatik veri çekme ve model eğitimi zamanlayıcısı.
- Her 30 dakikada bir: Kandilli Live API'den veri çek
- Günde bir kez: Modeli yeniden eğit
"""

import time
import threading
from datetime import datetime

# Proje modülleri
from data_collector import fetch_live_data, fetch_archive_data, generate_synthetic_data
from dataset_manager import (
    load_dataset, add_earthquakes, add_training_records,
    get_training_records, DEFAULT_DATASET_FILE
)
from train_models import train_all

# Zamanlama sabitleri (saniye)
DATA_COLLECTION_INTERVAL = 30 * 60   # 30 dakika
MODEL_TRAINING_INTERVAL = 24 * 60 * 60  # 24 saat (1 gün)


def _run_data_collection():
    """
    Kandilli API'lerden veri çeker ve earthquake_history.json'a ekler.
    Duplicate kontrolü dataset_manager tarafından yapılır.
    """
    print(f"[SCHEDULER] Veri toplama başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. Live API
        live_earthquakes = fetch_live_data()
        added_live, total = add_earthquakes(live_earthquakes, source='kandilli')
        
        # 2. Archive API (ek veri)
        archive_earthquakes = fetch_archive_data()
        add_earthquakes(archive_earthquakes, source='kandilli')
        
        # 3. Şehir bazlı eğitim verisi oluştur (app modülü gerekli)
        try:
            from app import (
                TURKEY_CITIES, extract_features, predict_earthquake_risk
            )
            all_eq = live_earthquakes + archive_earthquakes
            if all_eq:
                training_records = []
                for city_name, city_data in TURKEY_CITIES.items():
                    lat = city_data['lat']
                    lon = city_data['lon']
                    features = extract_features(all_eq, lat, lon, time_window_hours=168)
                    if features and features.get('count', 0) > 0:
                        risk_result = predict_earthquake_risk(all_eq, lat, lon)
                        training_records.append({
                            'city': city_name,
                            'lat': lat,
                            'lon': lon,
                            'features': features,
                            'risk_score': risk_result.get('risk_score', 2.0),
                            'timestamp': time.time()
                        })
                if training_records:
                    add_training_records(training_records)
        except ImportError:
            print("[SCHEDULER] app modülü yok, sadece ham deprem verisi eklendi")
        
        # 4. Veri azsa sentetik ekle
        records = get_training_records()
        if len(records) < 50:
            synthetic = generate_synthetic_data(num_samples=100)
            add_training_records(synthetic)
        
        print(f"[SCHEDULER] Veri toplama tamamlandı")
    except Exception as e:
        print(f"[SCHEDULER] Veri toplama hatası: {e}")
        import traceback
        traceback.print_exc()


def _run_model_training():
    """Model eğitimini çalıştırır."""
    print(f"[SCHEDULER] Model eğitimi başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        version = train_all()
        if version:
            print(f"[SCHEDULER] Model eğitimi tamamlandı: {version}")
        else:
            print("[SCHEDULER] Model eğitimi başarısız")
    except Exception as e:
        print(f"[SCHEDULER] Model eğitimi hatası: {e}")
        import traceback
        traceback.print_exc()


def run_scheduler():
    """
    Ana scheduler döngüsü.
    - Her 30 dakikada veri çeker
    - Günde bir kez model eğitir
    """
    print("="*60)
    print("SCHEDULER BAŞLATILDI")
    print(f"- Veri toplama: Her {DATA_COLLECTION_INTERVAL//60} dakikada")
    print(f"- Model eğitimi: Her {MODEL_TRAINING_INTERVAL//3600} saatte")
    print("="*60)
    
    last_data_collection = 0
    last_model_training = 0
    
    while True:
        try:
            now = time.time()
            
            # Veri toplama (her 30 dakika)
            if now - last_data_collection >= DATA_COLLECTION_INTERVAL:
                _run_data_collection()
                last_data_collection = now
            
            # Model eğitimi (günde bir)
            if now - last_model_training >= MODEL_TRAINING_INTERVAL:
                _run_model_training()
                last_model_training = now
            
            # 5 dakikada bir kontrol
            time.sleep(300)
            
        except KeyboardInterrupt:
            print("\n[SCHEDULER] Durduruluyor...")
            break
        except Exception as e:
            print(f"[SCHEDULER] Hata: {e}")
            time.sleep(60)


def run_scheduler_background():
    """Scheduler'ı arka planda thread olarak çalıştırır."""
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    print("[SCHEDULER] Arka plan thread başlatıldı")
    return thread


if __name__ == "__main__":
    # İlk çalıştırmada hemen veri topla ve eğit
    print("İlk veri toplama ve eğitim...")
    _run_data_collection()
    _run_model_training()
    
    # Sonra scheduler'ı başlat
    run_scheduler()
