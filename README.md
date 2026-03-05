# 🚀 Üst Düzey Yapay Zeka Destekli Deprem İzleme Sistemi

Türkiye için gelişmiş makine öğrenmesi destekli deprem izleme ve erken uyarı sistemi.

## ✨ Özellikler

- 🤖 **Gelişmiş ML Modelleri**: Random Forest + XGBoost + LightGBM Ensemble
- 🏛️ **İstanbul Erken Uyarı Sistemi**: Özel algoritma ile 24-72 saat önceden uyarı
- 📊 **Feature Engineering**: 27+ özellik (ETAS, cluster, komşu aktivite dahil)
- 🔍 **Anomali Tespiti**: Isolation Forest ile olağandışı aktivite tespiti
- 🏙️ **İl Bazında Hasar Tahmini**: 81 il için otomatik analiz
- 📱 **WhatsApp Bildirimleri**: Twilio entegrasyonu ile anında uyarı
- 🗺️ **Görselleştirme**: Aktif fay hatları ve risk bölgeleri haritası

## 🚀 Hızlı Başlangıç

### Yerel Kurulum

1. **Repository'yi klonlayın:**
```bash
git clone https://github.com/kullaniciadi/deprem-izleme-sistemi.git
cd deprem-izleme-sistemi
```

2. **Sanal ortam oluşturun:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

4. **Ortam değişkenlerini ayarlayın:**
```bash
# Windows PowerShell
$env:TWILIO_ACCOUNT_SID="your_account_sid"
$env:TWILIO_AUTH_TOKEN="your_auth_token"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"
```

5. **Veri toplama (opsiyonel, 26k+ deprem):**
```bash
python collect_large_dataset.py
```

6. **Model eğitimi:**
```bash
python train_models.py
```

7. **Uygulamayı çalıştırın:**
```bash
python app.py
```

8. **Frontend'i açın:**
Tarayıcıda `index.html` dosyasını açın.

## 🌐 Render.com'da Deploy

### 1. GitHub'a Yükleyin

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/kullaniciadi/deprem-izleme-sistemi.git
git push -u origin main
```

### 2. Render.com'da Servis Oluşturun

1. **Render.com'a giriş yapın:** https://render.com
2. **"New +"** butonuna tıklayın
3. **"Web Service"** seçin
4. **GitHub repository'nizi bağlayın**
5. **Ayarları yapılandırın:**
   - **Name:** `deprem-izleme-sistemi`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

### 3. Ortam Değişkenlerini Ayarlayın

Render.com dashboard'da **"Environment"** sekmesine gidin ve şunları ekleyin:

```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
PORT=10000
```

### 4. Deploy Edin

Render.com otomatik olarak deploy edecek. İlk deploy 5-10 dakika sürebilir.

## 📁 Proje Yapısı

```
DepremAnaliz/
├── app.py                    # Flask backend
├── train_models.py           # ML eğitim pipeline
├── earthquake_features.py    # Feature engineering (ETAS, cluster)
├── collect_large_dataset.py # USGS 1990-2026 veri toplama
├── dataset_manager.py       # Veri yönetimi, dedup
├── ml_architectures.py      # Ensemble, LSTM, ETAS mimarileri
├── models/                   # Eğitilmiş modeller
├── requirements.txt
└── README.md
```

## 🔧 Yapılandırma

### Twilio Ayarları

1. **Twilio hesabı oluşturun:** https://www.twilio.com
2. **WhatsApp Sandbox'ı aktifleştirin**
3. **Kimlik bilgilerini alın:**
   - Account SID
   - Auth Token
   - WhatsApp Sandbox numarası
4. **Ortam değişkenlerine ekleyin**

Detaylı kurulum için: [TWILIO_HIZLI_KURULUM.md](TWILIO_HIZLI_KURULUM.md)

## 📊 Model Performansı

- **Ana Model:** XGBoost Regressor (risk skoru tahmini)
- **Accuracy:** ~0.72–0.73 (risk sınıfı: düşük/orta/yüksek/çok yüksek)
- **Feature Sayısı:** 27 (ETAS, cluster, neighbor_activity dahil)
- **Eğitim Verisi:** ~121.000 kayıt (tarihsel genişletme ile 26k depremden)
- **Veri Kaynağı:** USGS 1990–2026 arşiv, Kandilli, EMSC

## 🎯 API Endpoints

- `GET /api/risk` - Risk analizi
- `GET /api/fault-lines` - Fay hatları
- `POST /api/predict-risk` - ML destekli risk tahmini
- `GET /api/istanbul-early-warning` - İstanbul erken uyarı
- `POST /api/anomaly-detection` - Anomali tespiti
- `POST /api/city-damage-analysis` - İl bazında hasar analizi
- `POST /api/set-alert` - WhatsApp bildirim ayarları
- `POST /api/train-models` - Model eğitimi

## 📝 Lisans

Bu proje eğitim ve araştırma amaçlıdır.

## 🤝 Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır. Büyük değişiklikler için önce bir issue açın.

## 📞 Destek

Sorularınız için issue açabilirsiniz.

---

**Not:** Bu sistem eğitim amaçlıdır. Gerçek deprem uyarıları için resmi kurumları takip edin.
