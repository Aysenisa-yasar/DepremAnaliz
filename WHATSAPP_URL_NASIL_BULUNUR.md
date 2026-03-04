# 🔍 WhatsApp Servisi URL'ini Nasıl Bulursunuz?

## 📍 Render.com'da URL Bulma

### Yöntem 1: Settings Sekmesinden (Önerilen)

1. **Render.com Dashboard**'a gidin
2. **"whatsapp-service"** servisini bulun ve tıklayın
3. Üstteki sekmelerden **"Settings"** sekmesine tıklayın
4. **"Service Details"** veya **"Service Information"** bölümüne gidin
5. **"URL"** veya **"Service URL"** kısmını bulun
6. URL şu formatta olacak:
   ```
   https://whatsapp-service-xxxx.onrender.com
   ```
   veya
   ```
   https://whatsapp-service.onrender.com
   ```
7. Bu URL'yi kopyalayın

### Yöntem 2: Dashboard'dan Direkt

1. **Render.com Dashboard**'a gidin
2. **"whatsapp-service"** servisinin yanında URL görünebilir
3. URL'in üzerine tıklayarak kopyalayabilirsiniz

### Yöntem 3: Logs Sekmesinden

1. **Render.com Dashboard** → **"whatsapp-service"** servisi
2. **"Logs"** sekmesine gidin
3. Loglarda şu mesajı arayın:
   ```
   [Server] WhatsApp servisi 3001 portunda çalışıyor
   [Server] Durum: http://localhost:3001/status
   ```
4. Render.com otomatik olarak servise bir URL atar, bu URL'i Settings'ten bulabilirsiniz

---

## 📋 URL Formatı

WhatsApp servisi URL'i genellikle şu formatta olur:

```
https://whatsapp-service-xxxx.onrender.com
```

veya

```
https://whatsapp-service.onrender.com
```

**NOT:** `xxxx` kısmı Render.com tarafından otomatik oluşturulan bir ID'dir.

---

## ✅ URL'i Doğrulama

URL'i bulduktan sonra test edin:

1. Tarayıcınızda şu URL'yi açın:
   ```
   https://whatsapp-service-xxxx.onrender.com/status
   ```

2. Şu cevabı almalısınız:
   ```json
   {
     "ready": false,
     "authenticated": false,
     "hasQr": true
   }
   ```

3. Eğer bu cevabı alıyorsanız, URL doğru! ✅

---

## 🔧 Flask Backend'e URL Ekleme

URL'i bulduktan sonra:

1. **Render.com Dashboard** → **deprem-izleme-sistemi** servisi
2. **Environment** sekmesine gidin
3. **"+ Add"** butonuna tıklayın
4. **Key:** `WHATSAPP_WEB_SERVICE_URL`
5. **Value:** Bulduğunuz URL'i yapıştırın (örn: `https://whatsapp-service-xxxx.onrender.com`)
6. **"Save"** butonuna tıklayın
7. **"Save, rebuild, and deploy"** butonuna tıklayın

---

## ⚠️ Önemli Notlar

1. **URL Formatı:**
   - ✅ Doğru: `https://whatsapp-service-xxxx.onrender.com`
   - ❌ Yanlış: `http://whatsapp-service-xxxx.onrender.com` (https olmalı)
   - ❌ Yanlış: `whatsapp-service-xxxx.onrender.com` (https:// eklenmeli)

2. **URL Değişmez:**
   - Render.com'da servis oluşturulduktan sonra URL sabit kalır
   - Servis adını değiştirirseniz URL de değişebilir

3. **Free Plan:**
   - Render.com Free Plan'da URL formatı: `https://servis-adi-xxxx.onrender.com`
   - Pro Plan'da özel domain kullanabilirsiniz

---

## 🎯 Adım Adım Özet

1. Render.com Dashboard → **whatsapp-service** servisi
2. **Settings** sekmesi
3. **Service Details** → **URL** kısmını bulun
4. URL'i kopyalayın
5. Flask backend → **Environment** → `WHATSAPP_WEB_SERVICE_URL` ekleyin
6. URL'i yapıştırın ve kaydedin

---

## 🧪 Test

URL'i ekledikten sonra:

1. Frontend'i yenileyin (F5)
2. "📱 WhatsApp QR Kod ile Bağlan" butonuna tıklayın
3. QR kod görünmeli ✅

Eğer hala 503 hatası alıyorsanız:
- WhatsApp servisi deploy edilmiş mi kontrol edin
- WhatsApp servisi çalışıyor mu kontrol edin (Logs sekmesi)
- URL doğru mu kontrol edin (`/status` endpoint'ini test edin)
