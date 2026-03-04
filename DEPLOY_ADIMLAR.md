# 🚀 WhatsApp QR Kod ile Otomatik Bildirim - Deploy Adımları

## ✅ Evet, QR kod ile otomatik bildirim alabilirsiniz!

Ancak **2 servis** deploy etmeniz gerekiyor:

1. **Flask Backend** (Python) - Zaten deploy edilmiş ✅
2. **WhatsApp Servisi** (Node.js) - Şimdi deploy edeceğiz

## 📋 Adım Adım Deploy

### 1. Render.com'da WhatsApp Servisi Oluştur

1. Render.com Dashboard'a gidin
2. **"New +"** butonuna tıklayın
3. **"Web Service"** seçin
4. Repository'yi bağlayın (aynı repo)
5. Ayarları yapın:

#### Temel Ayarlar:
- **Name**: `whatsapp-service` (veya istediğiniz isim)
- **Environment**: `Node`
- **Region**: İstediğiniz bölge
- **Branch**: `main`

#### Build & Deploy:
- **Build Command**: `npm install`
- **Start Command**: `node whatsapp-service.js`
- **Auto-Deploy**: `Yes` (otomatik deploy için)

#### Environment Variables:
```
NODE_VERSION=18.17.0
PORT=3001
```

6. **"Create Web Service"** butonuna tıklayın

### 2. Flask Backend Ortam Değişkenlerini Güncelle

Flask backend'inizde (deprem-izleme-sistemi) şu ortam değişkenlerini ekleyin:

1. Render.com Dashboard > **deprem-izleme-sistemi** servisi
2. **Environment** sekmesine gidin
3. Şu değişkenleri ekleyin:

```
USE_WHATSAPP_WEB=true
WHATSAPP_WEB_SERVICE_URL=https://whatsapp-service.onrender.com
```

**NOT:** `whatsapp-service.onrender.com` yerine kendi WhatsApp servisinizin URL'ini yazın.

### 3. QR Kod ile Bağlan

1. WhatsApp servisi deploy olduktan sonra:
   - Frontend'inize gidin (GitHub Pages)
   - "📱 WhatsApp QR Kod ile Bağlan" butonuna tıklayın
   - QR kod görünecek

2. WhatsApp'tan QR kodu okutun:
   - WhatsApp'ı telefonunuzda açın
   - **Ayarlar** > **Bağlı Cihazlar** > **Cihaz Bağla**
   - QR kodu okutun

3. Bağlantı başarılı olunca:
   - Frontend'de "✅ WhatsApp Bağlı" yazacak
   - Artık otomatik bildirimler gönderilecek!

## 🔔 Otomatik Bildirimler Nasıl Çalışır?

1. **Konumunuzu belirleyin** (Frontend'den)
2. **WhatsApp numaranızı girin** (+90 ile başlamalı)
3. **Ayarları kaydedin**
4. **QR kod ile WhatsApp'ı bağlayın**
5. Artık:
   - M ≥ 5.0 depremlerde 150 km içindeyse bildirim alırsınız
   - İstanbul erken uyarı sistemi aktifse önceden uyarı alırsınız

## ⚠️ Önemli Notlar

### WhatsApp Servisi Sürekli Çalışmalı

- Render.com Free Plan'da servisler 15 dakika kullanılmazsa uyku moduna geçer
- İlk istekte 30-60 saniye bekleme olabilir
- **Çözüm**: Render.com Pro Plan veya başka bir hosting (Heroku, Railway, vb.)

### QR Kod Yenileme

- WhatsApp bağlantısı kesilirse QR kod yeniden oluşturulur
- Frontend'den "📱 WhatsApp QR Kod ile Bağlan" butonuna tekrar tıklayın

### Oturum Kaydı

- WhatsApp oturumu `whatsapp-session` klasöründe saklanır
- Render.com'da bu klasör kalıcı olmalı (disk storage kullanın)

## 🧪 Test Etme

1. WhatsApp servisi çalışıyor mu?
   ```
   https://your-whatsapp-service.onrender.com/status
   ```
   Cevap: `{"ready":true,"authenticated":true}` olmalı

2. QR kod alınabiliyor mu?
   ```
   https://your-whatsapp-service.onrender.com/qr
   ```

3. Flask backend WhatsApp servisine bağlanabiliyor mu?
   - Frontend'den "📱 WhatsApp QR Kod ile Bağlan" butonuna tıklayın
   - QR kod görünmeli

## 🎉 Başarılı!

Artık QR kod ile WhatsApp'ı bağlayıp otomatik bildirimler alabilirsiniz!

## 📞 Sorun Giderme

### QR Kod Görünmüyor
- WhatsApp servisi deploy edilmiş mi kontrol edin
- `WHATSAPP_WEB_SERVICE_URL` doğru mu kontrol edin
- Browser console'da hata var mı bakın

### Bildirimler Gelmiyor
- WhatsApp bağlı mı kontrol edin (`/status` endpoint)
- Konumunuz kayıtlı mı kontrol edin
- Numara formatı doğru mu (+90 ile başlamalı)

### Servis Uyku Modunda
- İlk istekte 30-60 saniye bekleyin
- Render.com Pro Plan kullanın (sürekli çalışır)
