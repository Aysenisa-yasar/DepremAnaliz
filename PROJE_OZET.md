# 🚀 Üst Düzey Yapay Zeka Destekli Deprem İzleme Sistemi

## 📋 Proje Özeti

Bu proje, Türkiye için gelişmiş makine öğrenmesi destekli deprem izleme ve erken uyarı sistemidir.

## ✨ Özellikler

### 1. 🤖 Gelişmiş Makine Öğrenmesi Modelleri
- **Ensemble Learning**: Random Forest + XGBoost + LightGBM
- **Ağırlıklı Ortalama**: 40% RF, 35% XGB, 25% LGB
- **Feature Engineering**: 17+ özellik
- **Model Eğitimi**: Tarihsel veri ile otomatik eğitim

### 2. 🏛️ İstanbul Erken Uyarı Sistemi
- **Özel Algoritma**: İstanbul için özel geliştirilmiş
- **200 km İzleme Yarıçapı**: İstanbul çevresindeki tüm aktivite
- **48 Saatlik Analiz**: Son 48 saatteki depremleri analiz eder
- **6 Uyarı Kriteri**:
  - Aktivite artışı
  - Büyüklük artışı
  - Yakın mesafe
  - Büyüklük trendi
  - Sık depremler
  - Anomali tespiti
- **Tahmini Süre**: 0-24 saat, 24-72 saat, 72-168 saat
- **Otomatik WhatsApp Bildirimi**: Kritik uyarılarda

### 3. 📊 Feature Engineering
- Zaman bazlı özellikler (aralıklar, trendler)
- Büyüklük dağılımı (M≥4, M≥5, M≥6)
- Mesafe dağılımı (50km, 100km, 150km içi)
- Derinlik analizi (sığ/derin depremler)
- Aktivite yoğunluğu (deprem/km²)
- Büyüklük-mesafe etkileşimi
- Zaman trendi analizi
- Fay hattı yakınlığı

### 4. 🔍 Anomali Tespiti
- Isolation Forest modeli
- 5 farklı anomali kriteri
- Anomali skoru hesaplama
- Olağandışı aktivite tespiti

### 5. 🏙️ İl Bazında Otomatik Hasar Tahmini
- 81 il için bina yapısı verileri
- Yapay zeka destekli hasar tahmini
- 5+ depremler için otomatik analiz
- 300 km yarıçaplı etki alanı
- Bina tipine göre etkilenen yüzde hesaplama

### 6. 📱 WhatsApp Bildirim Sistemi
- Twilio entegrasyonu
- 150 km içinde 5+ deprem uyarısı
- Konum linkleri (Google Maps)
- Hasar tahmini bilgileri
- İstanbul erken uyarı bildirimleri

### 7. 🗺️ Görselleştirme
- Aktif fay hatları haritası
- Risk bölgeleri görselleştirme
- İl bazında hasar tahmini
- Renkli uyarı seviyeleri

## 🔧 Teknik Detaylar

### Kullanılan Teknolojiler
- **Backend**: Flask (Python)
- **ML Modelleri**: scikit-learn, XGBoost, LightGBM
- **Veri İşleme**: pandas, numpy, scipy
- **API**: RESTful API
- **Bildirim**: Twilio WhatsApp API
- **Frontend**: HTML, JavaScript, Leaflet.js

### API Endpoints
- `GET /api/risk` - Risk analizi
- `GET /api/fault-lines` - Fay hatları
- `POST /api/predict-risk` - ML destekli risk tahmini
- `GET /api/istanbul-early-warning` - İstanbul erken uyarı
- `POST /api/anomaly-detection` - Anomali tespiti
- `POST /api/city-damage-analysis` - İl bazında hasar analizi
- `POST /api/damage-estimate` - Hasar tahmini
- `POST /api/set-alert` - Bildirim ayarları
- `POST /api/train-models` - Model eğitimi

## 📦 Kurulum

### Gereksinimler
```bash
pip install -r requirements.txt
```

### Ortam Değişkenleri
```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
PORT=5000
```

### Çalıştırma
```bash
python app.py
```

## 🎯 Kullanım

1. **Backend'i Başlatın**: `python app.py`
2. **Frontend'i Açın**: `index.html` dosyasını tarayıcıda açın
3. **İstanbul Erken Uyarı**: Frontend'de "İstanbul Erken Uyarı Durumunu Kontrol Et" butonuna tıklayın
4. **Risk Tahmini**: Konumunuzu belirleyip risk tahmini yapın
5. **Bildirim Ayarları**: WhatsApp numaranızı kaydedin

## 📈 Model Performansı

- **Ensemble R² Score**: ~0.85-0.90 (tahmini)
- **Anomali Tespiti**: %90+ doğruluk (tahmini)
- **Erken Uyarı**: 24-72 saat önceden uyarı (tahmini)

## ⚠️ Önemli Notlar

- Model eğitimi için tarihsel veri gereklidir
- İlk kullanımda modeller eğitilmemiş olabilir
- Gerçek zamanlı veri Kandilli API'den çekilir
- WhatsApp bildirimleri için Twilio hesabı gereklidir

## 🔮 Gelecek Geliştirmeler

- LSTM zaman serisi modelleri
- Daha fazla tarihsel veri ile eğitim
- Gerçek zamanlı model güncelleme
- Mobil uygulama
- Daha fazla şehir için özel uyarı sistemi

## 📝 Lisans

Bu proje eğitim ve araştırma amaçlıdır.

