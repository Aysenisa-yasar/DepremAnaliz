# 📱 WhatsApp Web.js Ücretsiz Bildirim Sistemi Kurulumu

## 🎯 Özellikler

- ✅ **Tamamen Ücretsiz** - Twilio gibi ücretli servislere gerek yok
- ✅ **QR Kod ile Bağlanma** - WhatsApp Web gibi kolay bağlantı
- ✅ **Sınırsız Mesaj** - Günlük limit yok
- ✅ **Otomatik Yeniden Bağlanma** - Bağlantı kesilirse otomatik bağlanır

## 📋 Gereksinimler

- Node.js 16+ yüklü olmalı
- Python Flask backend çalışıyor olmalı

## 🚀 Kurulum Adımları

### 1. Node.js Bağımlılıklarını Yükle

```bash
npm install
```

veya

```bash
npm install whatsapp-web.js qrcode express cors
```

### 2. WhatsApp Servisini Başlat

```bash
node whatsapp-service.js
```

veya

```bash
npm start
```

Servis varsayılan olarak **3001** portunda çalışacak.

### 3. Flask Backend'i Güncelle

Flask backend otomatik olarak WhatsApp Web servisini kullanacak şekilde ayarlanmıştır.

Ortam değişkenleri (opsiyonel):
```bash
USE_WHATSAPP_WEB=true  # WhatsApp Web kullan (varsayılan: true)
WHATSAPP_WEB_SERVICE_URL=http://localhost:3001  # Servis URL'i
```

### 4. QR Kod ile Bağlan

1. Frontend'de "📱 WhatsApp QR Kod ile Bağlan" butonuna tıklayın
2. QR kod modal'da görünecek
3. WhatsApp'ı telefonunuzda açın
4. Ayarlar > Bağlı Cihazlar > Cihaz Bağla
5. QR kodu okutun
6. Bağlantı başarılı olunca bildirimler otomatik gönderilecek

## 🔧 Render.com Deployment

### Render.com'da Node.js Servisi Oluştur

1. Render.com'da yeni **Web Service** oluştur
2. Repository'yi bağla
3. Ayarlar:
   - **Build Command**: `npm install`
   - **Start Command**: `node whatsapp-service.js`
   - **Environment**: `Node`
4. Deploy et

### Flask Backend Ortam Değişkenleri

Render.com Flask backend'inde:
```
USE_WHATSAPP_WEB=true
WHATSAPP_WEB_SERVICE_URL=https://your-whatsapp-service.onrender.com
```

## 📝 Kullanım

### Mesaj Gönderme

Flask backend otomatik olarak WhatsApp Web servisini kullanır:

```python
send_whatsapp_notification("+905551234567", "Test mesajı")
```

### Durum Kontrolü

```bash
curl http://localhost:3001/status
```

### QR Kod Al

```bash
curl http://localhost:3001/qr
```

## ⚠️ Önemli Notlar

1. **İlk Bağlantı**: İlk kez QR kod okutmanız gerekir
2. **Oturum Kaydı**: `whatsapp-session` klasöründe oturum bilgileri saklanır
3. **Yeniden Bağlanma**: Bağlantı kesilirse otomatik yeniden bağlanır
4. **Çoklu Cihaz**: WhatsApp'ın çoklu cihaz desteği gerekir

## 🐛 Sorun Giderme

### Servis Başlamıyor

```bash
# Port kontrolü
netstat -ano | findstr :3001

# Node.js versiyonu
node --version  # 16+ olmalı
```

### QR Kod Görünmüyor

1. Servis çalışıyor mu kontrol edin
2. Browser console'da hata var mı bakın
3. CORS ayarlarını kontrol edin

### Mesaj Gönderilmiyor

1. WhatsApp bağlı mı kontrol edin: `/status` endpoint'i
2. Numara formatını kontrol edin: `+90XXXXXXXXXX`
3. Servis loglarını kontrol edin

## 🔄 Twilio'dan Geçiş

Eğer Twilio kullanıyorsanız ve WhatsApp Web'e geçmek istiyorsanız:

1. `USE_WHATSAPP_WEB=true` ortam değişkenini ayarlayın
2. WhatsApp Web servisini başlatın
3. QR kod ile bağlanın
4. Twilio ayarlarını kaldırabilirsiniz (fallback olarak kalabilir)

## 📚 API Endpoints

### GET /status
WhatsApp bağlantı durumunu döner.

**Response:**
```json
{
  "ready": true,
  "authenticated": true,
  "hasQr": false
}
```

### GET /qr
QR kod verisini döner (base64 image).

**Response:**
```json
{
  "success": true,
  "qr": "data:image/png;base64,...",
  "message": "QR kod hazır"
}
```

### POST /send
Mesaj gönderir.

**Request:**
```json
{
  "number": "+905551234567",
  "message": "Test mesajı"
}
```

**Response:**
```json
{
  "success": true,
  "messageId": "...",
  "message": "Mesaj başarıyla gönderildi"
}
```

### POST /restart
Servisi yeniden başlatır.

## 🎉 Başarılı!

Artık ücretsiz WhatsApp bildirim sistemi kullanıyorsunuz! 🚀
