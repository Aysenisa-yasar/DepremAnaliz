# 📋 Render.com'da Environment Variables Ekleme - Adım Adım

## 🔵 Flask Backend (deprem-izleme-sistemi) için:

### Adım 1: Servise Git
1. **Render.com Dashboard**'a gidin
2. **"DepremAnaliz"** (veya **deprem-izleme-sistemi**) servisini bulun
3. Servis adına **tıklayın** (mavi link)

### Adım 2: Environment Sekmesine Git
1. Servis sayfasında üstteki sekmelerden **"Environment"** sekmesine tıklayın
2. Veya sol menüden **"Environment"** seçeneğine tıklayın

### Adım 3: Environment Variable Ekle
1. **"+ Add"** butonuna tıklayın (sağ üst köşede veya tablonun altında)
2. **"KEY"** kutusuna değişken adını yazın (örn: `USE_WHATSAPP_WEB`)
3. **"VALUE"** kutusuna değeri yazın (örn: `true`)
4. **"Save"** butonuna tıklayın
5. Her değişken için bu adımları tekrarlayın

### Adım 4: Deploy Et
1. Tüm değişkenleri ekledikten sonra
2. **"Save, rebuild, and deploy"** butonuna tıklayın (sağ alt köşede)
3. Servis yeniden deploy edilecek

---

## 🟢 WhatsApp Servisi (whatsapp-service) için:

### Adım 1: Servise Git
1. **Render.com Dashboard**'a gidin
2. **"whatsapp-service"** servisini bulun
3. Servis adına **tıklayın** (mavi link)

### Adım 2: Environment Sekmesine Git
1. Servis sayfasında üstteki sekmelerden **"Environment"** sekmesine tıklayın
2. Veya sol menüden **"Environment"** seçeneğine tıklayın

### Adım 3: Environment Variable Ekle
1. **"+ Add"** butonuna tıklayın
2. İlk değişken:
   - **KEY:** `NODE_VERSION`
   - **VALUE:** `18.17.0`
   - **"Save"** butonuna tıklayın
3. İkinci değişken:
   - **KEY:** `PORT`
   - **VALUE:** `3001`
   - **"Save"** butonuna tıklayın

### Adım 4: Deploy Et
1. **"Save, rebuild, and deploy"** butonuna tıklayın
2. Servis yeniden deploy edilecek

---

## 📸 Görsel Rehber

### Environment Variables Sayfası Görünümü:

```
┌─────────────────────────────────────────┐
│  Environment Variables                  │
├─────────────────────────────────────────┤
│  KEY                    │  VALUE        │
├─────────────────────────────────────────┤
│  PORT                   │  10000        │  [👁️] [🗑️]
│  USE_WHATSAPP_WEB       │  true         │  [👁️] [🗑️]
│  WHATSAPP_WEB_SERVICE...│  https://...  │  [👁️] [🗑️]
├─────────────────────────────────────────┤
│  [+ Add]                                 │
└─────────────────────────────────────────┘
                    [Save, rebuild, and deploy]
```

---

## ✅ Eklenecek Değişkenler Listesi

### Flask Backend (deprem-izleme-sistemi):
```
USE_WHATSAPP_WEB = true
WHATSAPP_WEB_SERVICE_URL = https://whatsapp-service-xxxx.onrender.com
```

### WhatsApp Servisi (whatsapp-service):
```
NODE_VERSION = 18.17.0
PORT = 3001
```

---

## 🎯 Hızlı Özet

1. **Dashboard** → Servis adına tıklayın
2. **Environment** sekmesine gidin
3. **"+ Add"** butonuna tıklayın
4. **KEY** ve **VALUE** yazın
5. **"Save"** butonuna tıklayın
6. **"Save, rebuild, and deploy"** butonuna tıklayın

---

## ⚠️ Önemli Notlar

1. **"+ Add" Butonu:**
   - Tablonun altında veya sağ üst köşede olabilir
   - Bazen "Add Environment Variable" yazabilir

2. **Değişken İsimleri:**
   - Büyük/küçük harf duyarlı: `USE_WHATSAPP_WEB` (doğru)
   - Alt çizgi kullanın: `USE_WHATSAPP_WEB` (doğru)

3. **Değerler:**
   - Tırnak işareti kullanmayın: `true` (doğru), `"true"` (yanlış)
   - URL'ler için `https://` ekleyin

4. **Deploy:**
   - Değişkenler eklendikten sonra mutlaka **"Save, rebuild, and deploy"** butonuna tıklayın
   - Deploy işlemi 2-5 dakika sürebilir
