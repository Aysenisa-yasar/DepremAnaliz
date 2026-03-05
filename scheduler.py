#!/usr/bin/env python3
"""
scheduler.py
Otomatik veri çekme ve model eğitimi zamanlayıcısı.
- Her 30 dakikada bir: Kandilli Live API'den veri çek
- Günde bir kez: Modeli yeniden eğit
"""

import os
import time
import threading
from datetime import datetime

# Proje modülleri
from data_collector import (
    fetch_live_data, fetch_archive_data, fetch_all_multi_source,
    fetch_archive_full, generate_synthetic_data
)
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
        # 1. Veri yoksa veya azsa tam arşiv çek; yoksa multi-source
        data = load_dataset(DEFAULT_DATASET_FILE)
        raw_count = sum(1 for r in data if r.get('geojson') and r['geojson'].get('coordinates'))
        if raw_count < 500:
            print("[SCHEDULER] Veri az - tam arşiv çekiliyor (USGS + Kandilli)...")
            all_eq = fetch_archive_full()
        else:
            all_eq = fetch_all_multi_source()
        if all_eq:
            add_earthquakes(all_eq, source='multi')
        
        # 2. Şehir bazlı eğitim verisi (earthquake_features - app'ten bağımsız)
        from earthquake_features import create_training_records_from_earthquakes
        if all_eq:
            training_records = create_training_records_from_earthquakes(all_eq)
            if training_records:
                add_training_records(training_records)
                print(f"[SCHEDULER] {len(training_records)} şehir için eğitim kaydı eklendi")
        
        # 4. Veri azsa sentetik ekle (bootstrap+noise tercih)
        records = get_training_records(filepath=DEFAULT_DATASET_FILE)
        if len(records) < 50:
            synthetic = generate_synthetic_data(num_samples=100, real_records=records)
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
    last_model_training = time.time()  # İlk 24 saat bekle, hemen eğitme

    while True:
        try:
            now = time.time()

            # Veri toplama (her 30 dakika)
            if now - last_data_collection >= DATA_COLLECTION_INTERVAL:
                _run_data_collection()
                last_data_collection = now

            # Model eğitimi: SADECE 24 saatte bir (veri toplamadan SONRA tetiklenmez)
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


def _model_exists() -> bool:
    """Model dosyası var mı kontrol et."""
    try:
        from train_models import get_latest_model_path
        return get_latest_model_path() is not None
    except ImportError:
        return os.path.exists('models') and any(
            f.startswith('model_v') and f.endswith('.pkl')
            for f in os.listdir('models')
        )


if __name__ == "__main__":
    # İlk çalıştırmada veri topla
    print("İlk veri toplama başlatılıyor...")
    _run_data_collection()
    # Model yoksa bir kez eğit (ilk kurulum)
    if not _model_exists():
        print("Model bulunamadı - ilk kurulum için bir kez eğitim yapılıyor...")
        _run_model_training()
    else:
        print("Mevcut model bulundu - eğitim 24 saat sonra yapılacak.")
    run_scheduler()
