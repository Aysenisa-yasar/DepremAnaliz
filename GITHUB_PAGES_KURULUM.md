# 🌐 GitHub Pages ile Site Yayınlama

## 📋 Adım Adım Kurulum

### 1. GitHub Repository Settings'e Gidin

1. **Repository sayfanıza gidin:** https://github.com/Aysenisa-yasar/DepremAnaliz
2. **"Settings" sekmesine tıklayın** (üst menüde)
3. Sol menüden **"Pages"** seçeneğine tıklayın

### 2. GitHub Pages'i Aktifleştirin

1. **"Source"** bölümünde:
   - **Branch:** `main` seçin
   - **Folder:** `/ (root)` seçin
2. **"Save"** butonuna tıklayın

### 3. Site URL'ini Alın

GitHub Pages URL'i şu formatta olacak:
```
https://aysenisa-yasar.github.io/DepremAnaliz/
```

**Not:** İlk aktifleştirmeden sonra 1-2 dakika sürebilir.

### 4. Frontend'i Render.com Backend'e Bağlayın

Frontend (GitHub Pages) ve Backend (Render.com) farklı domain'lerde olduğu için CORS ayarları zaten yapılmış. Sadece API URL'ini güncellemeniz gerekebilir.

## 🔧 API URL Güncelleme

`script.js` dosyasında API URL'i otomatik olarak algılanıyor:
- Localhost'ta: `http://localhost:5000`
- Production'da: Aynı domain'i kullanır

Eğer Render.com URL'ini manuel olarak ayarlamak isterseniz:

```javascript
// script.js dosyasının başında
const API_URL = 'https://your-render-app.onrender.com';
```

## ✅ Kontrol Listesi

- [ ] GitHub Pages aktifleştirildi
- [ ] Site URL'i alındı: `https://aysenisa-yasar.github.io/DepremAnaliz/`
- [ ] Render.com backend URL'i hazır
- [ ] Frontend test edildi
- [ ] API bağlantıları çalışıyor

## 🎯 Sonuç

- **Frontend:** https://aysenisa-yasar.github.io/DepremAnaliz/
- **Backend:** https://your-render-app.onrender.com

Her ikisi de çalışıyor olacak!


