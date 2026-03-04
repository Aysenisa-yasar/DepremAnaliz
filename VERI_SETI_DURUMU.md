# 📊 Veri Seti Durumu - Detaylı Rapor

## ✅ Şu Anki Durum

### 1. Kandilli API'den Veri Çekme
**Durum:** ✅ **AKTİF ve ÇALIŞIYOR**

- **API URL:** `https://api.orhanaydogdu.com.tr/deprem/kandilli/live`
- **Kullanım:** Her API çağrısında kullanılıyor
- **Cache:** 5 dakika cache mevcut (performans için)
- **Retry:** 2 kez retry mekanizması var

**Kullanıldığı Yerler:**
- ✅ Frontend harita verileri (her istekte)
- ✅ Risk tahmini (her istekte)
- ✅ Büyük deprem kontrolü (her 30 saniyede bir)
- ✅ Sürekli veri toplama (her 30 dakikada bir)

---

### 2. Sürekli Veri Toplama Sistemi
**Durum:** ✅ **AKTİF ve ÇALIŞIYOR**

**Nasıl Çalışıyor:**
- Her **30 dakikada bir** otomatik çalışır
- Kandilli API'den güncel deprem verilerini çeker
- **81 il** için özellik çıkarır (feature extraction)
- Risk skoru hesaplar
- `earthquake_history.json` dosyasına kaydeder

**Veri Formatı:**
```json
{
  "city": "İstanbul",
  "lat": 41.0082,
  "lon": 28.9784,
  "features": {
    "count": 15,
    "max_magnitude": 4.5,
    "min_distance": 25.3,
    ...
  },
  "risk_score": 6.2,
  "timestamp": 1703123456.789
}
```

**Veri Seti Özellikleri:**
- ✅ Son 7 günlük deprem verileri kullanılıyor
- ✅ Duplicate kontrolü var (son 1 saat içinde aynı şehir için veri varsa atlanır)
- ✅ Maksimum 10,000 kayıt tutuluyor (dosya boyutu kontrolü)
- ✅ Her kayıt şehir bazlı (81 il)

---

### 3. Model Eğitimi
**Durum:** ⚠️ **MANUEL EĞİTİM** (otomatik değil)

**Mevcut Durum:**
- Model eğitimi için `train_risk_prediction_model()` fonksiyonu var
- Ancak **otomatik eğitim yok**
- Manuel olarak `/api/train-models` endpoint'i çağrılmalı

**Model Türleri:**
1. **Random Forest** (n_estimators=100, max_depth=10)
2. **XGBoost** (n_estimators=100, max_depth=6, learning_rate=0.1)
3. **LightGBM** (n_estimators=100, max_depth=6, learning_rate=0.1)
4. **Ensemble** (ağırlıklı ortalama: 40% RF + 35% XGB + 25% LGB)

**Eğitim İçin Gereksinimler:**
- Minimum 50 kayıt gerekli
- `earthquake_history.json` dosyasından veri okunur
- Model `risk_prediction_model.pkl` dosyasına kaydedilir

---

### 4. Model Kullanımı (Tahmin)
**Durum:** ✅ **AKTİF ve ÇALIŞIYOR**

**Nasıl Çalışıyor:**
- Eğitilmiş model varsa (`risk_prediction_model.pkl`):
  - ✅ **ML Ensemble** kullanılır (Random Forest + XGBoost + LightGBM)
  - ✅ Güncel Kandilli verileri ile özellik çıkarılır
  - ✅ Model tahmin yapar
- Eğitilmiş model yoksa:
  - ⚠️ **Geleneksel yöntem** kullanılır (basit hesaplama)

**Özellik Çıkarma:**
- Son 24 saatlik deprem verileri analiz edilir
- 17 farklı özellik çıkarılır:
  - Deprem sayısı, büyüklükler, mesafeler
  - Derinlik, zaman aralıkları
  - Fay hattı mesafesi
  - Aktivite yoğunluğu
  - vs.

---

## 📈 Veri Seti İstatistikleri

### Toplanan Veri:
- **Kaynak:** Kandilli Rasathanesi (via orhanaydogdu.com.tr API)
- **Sıklık:** Her 30 dakikada bir
- **Kapsam:** 81 il (Türkiye'nin tüm illeri)
- **Zaman Penceresi:** Son 7 günlük deprem verileri
- **Maksimum Kayıt:** 10,000 kayıt (en eski kayıtlar silinir)

### Eğitim Verisi:
- **Dosya:** `earthquake_history.json`
- **Format:** JSON (her kayıt şehir bazlı)
- **Özellikler:** 17 farklı özellik
- **Hedef:** Risk skoru (0-10 arası)

---

## 🔄 Veri Akışı

```
Kandilli API
    ↓
fetch_earthquake_data_with_retry()
    ↓
┌─────────────────────────────────┐
│ 1. Frontend İstekleri           │ → Harita, Risk Tahmini
│ 2. Büyük Deprem Kontrolü         │ → Bildirimler (30 saniye)
│ 3. Sürekli Veri Toplama          │ → Eğitim Verisi (30 dakika)
└─────────────────────────────────┘
    ↓
earthquake_history.json
    ↓
train_risk_prediction_model()
    ↓
risk_prediction_model.pkl
    ↓
predict_earthquake_risk() (ML Ensemble)
```

---

## ✅ Güncel Kullanım

### Eğitimde Güncel Veriler Kullanılıyor mu?

**CEVAP:** ⚠️ **KISMEN**

**Açıklama:**
1. ✅ **Veri toplama:** Güncel (her 30 dakikada bir Kandilli'den çekiliyor)
2. ✅ **Tahmin:** Güncel (her istekte Kandilli'den güncel veri çekiliyor)
3. ⚠️ **Model eğitimi:** Manuel (otomatik değil, `/api/train-models` çağrılmalı)

**Yani:**
- Tahmin yaparken **güncel veriler** kullanılıyor ✅
- Model eğitimi için **toplanan veriler** kullanılıyor ✅
- Ancak model **otomatik yeniden eğitilmiyor** ⚠️

---

## 🔧 İyileştirme Önerileri

### 1. Otomatik Model Eğitimi
Model eğitimini otomatikleştirebiliriz:
- Her 24 saatte bir otomatik eğitim
- Veya veri seti belirli bir büyüklüğe ulaştığında eğitim

### 2. Veri Seti Büyüklüğü
- Şu an maksimum 10,000 kayıt
- Daha fazla veri için limit artırılabilir

### 3. Veri Kalitesi
- Duplicate kontrolü var ✅
- Ancak veri doğrulama eklenebilir

---

## 📊 Özet

| Özellik | Durum | Açıklama |
|---------|-------|----------|
| Kandilli API | ✅ Aktif | Her istekte güncel veri çekiliyor |
| Veri Toplama | ✅ Aktif | Her 30 dakikada bir otomatik |
| Veri Seti | ✅ Güncel | `earthquake_history.json` sürekli güncelleniyor |
| Model Eğitimi | ⚠️ Manuel | Otomatik değil, manuel çağrılmalı |
| Model Kullanımı | ✅ Aktif | Eğitilmiş model varsa kullanılıyor |
| Tahmin Verisi | ✅ Güncel | Her istekte Kandilli'den güncel veri |

---

## 🎯 Sonuç

**Kandilli'den veri çekme:** ✅ **GÜNCEL ve ÇALIŞIYOR**
- Her istekte güncel veri çekiliyor
- Sürekli veri toplama aktif
- Veri seti sürekli güncelleniyor

**Eğitimde kullanım:** ⚠️ **KISMEN GÜNCEL**
- Veri toplama güncel ✅
- Model eğitimi manuel ⚠️
- Tahmin yaparken güncel veriler kullanılıyor ✅

**Öneri:** Model eğitimini otomatikleştirmek için kod ekleyebilirim. İster misiniz?
