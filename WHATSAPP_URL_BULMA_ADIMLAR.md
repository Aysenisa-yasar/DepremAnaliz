# 🔍 WhatsApp Servisi URL'ini Bulma - Adım Adım

## ⚠️ ÖNEMLİ: Workspace Settings'te Değil!

Şu anda **Workspace Settings** sayfasındasınız. WhatsApp servisi URL'ini bulmak için **servis sayfasına** gitmeniz gerekiyor.

---

## 📍 Doğru Yol: Servis Sayfasına Gitme

### Adım 1: Dashboard'a Dönün
1. Sol menüden **"Projects"** veya **"Services"** sekmesine tıklayın
2. Veya üstteki **"Render"** logosuna tıklayın (Dashboard'a döner)

### Adım 2: WhatsApp Servisini Bulun
1. Dashboard'da **"whatsapp-service"** servisini bulun
2. Servis adına tıklayın (mavi link)

### Adım 3: Settings Sekmesine Gidin
1. Servis sayfasında üstteki sekmelerden **"Settings"** sekmesine tıklayın
2. Veya sol menüden **"Settings"** seçeneğine tıklayın

### Adım 4: URL'i Bulun
1. **"Service Details"** veya **"Service Information"** bölümüne gidin
2. **"URL"** veya **"Service URL"** kısmını bulun
3. URL şu formatta olacak:
   ```
   https://whatsapp-service-xxxx.onrender.com
   ```
4. Bu URL'yi kopyalayın

---

## 🎯 Alternatif: Dashboard'dan Direkt

1. **Render.com Dashboard**'a gidin
2. **"Services"** listesinde **"whatsapp-service"** servisini bulun
3. Servis adının yanında veya altında URL görünebilir
4. URL'in üzerine tıklayarak kopyalayabilirsiniz

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

## 🗺️ Navigasyon Yolu

```
Render.com Dashboard
    ↓
Services (sol menü veya üst menü)
    ↓
whatsapp-service (servis adına tıklayın)
    ↓
Settings (sekme)
    ↓
Service Details
    ↓
URL (kopyalayın)
```

---

## ⚠️ Önemli Notlar

1. **Workspace Settings ≠ Servis Settings:**
   - Workspace Settings: Tüm workspace için genel ayarlar
   - Servis Settings: Her servis için özel ayarlar (URL burada)

2. **URL Formatı:**
   - ✅ Doğru: `https://whatsapp-service-xxxx.onrender.com`
   - ❌ Yanlış: `http://whatsapp-service-xxxx.onrender.com` (https olmalı)
   - ❌ Yanlış: `whatsapp-service-xxxx.onrender.com` (https:// eklenmeli)

3. **Eğer Servis Görünmüyorsa:**
   - WhatsApp servisi henüz oluşturulmamış olabilir
   - Önce WhatsApp servisini oluşturmanız gerekir (WHATSAPP_SERVISI_DEPLOY.md'ye bakın)

---

## 🎯 Hızlı Özet

1. **Dashboard** → **Services** → **whatsapp-service**
2. **Settings** sekmesi
3. **Service Details** → **URL** kısmını bulun
4. URL'i kopyalayın
5. Flask backend → **Environment** → `WHATSAPP_WEB_SERVICE_URL` ekleyin
