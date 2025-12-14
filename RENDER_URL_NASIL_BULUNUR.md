# 🔗 Render.com Site URL'si Nasıl Bulunur?

## 📍 URL'yi Bulma Yöntemleri

### Yöntem 1: Render.com Dashboard'dan (En Kolay)

1. **Render.com dashboard'a gidin:** https://dashboard.render.com
2. **Servisinize tıklayın** (oluşturduğunuz web service)
3. **Üst kısımda URL görünecek:**
   ```
   https://servis-adi.onrender.com
   ```
4. **URL'in yanında kopyala ikonu var** - tıklayarak kopyalayabilirsiniz

### Yöntem 2: Deploy Loglarından

1. Servis sayfanızda **"Logs"** sekmesine gidin
2. Deploy tamamlandığında şu mesajı göreceksiniz:
   ```
   Your service is live at https://servis-adi.onrender.com
   ```

### Yöntem 3: Settings'ten

1. Servis sayfanızda **"Settings"** sekmesine gidin
2. **"Service Details"** bölümünde URL görünecek

## 📝 URL Formatı

Render.com URL'leri genellikle şu formattadır:
```
https://[servis-adi].onrender.com
```

Örnek:
- `https://deprem-analiz.onrender.com`
- `https://deprem-izleme-sistemi.onrender.com`
- `https://deprem-analiz-xxxx.onrender.com` (otomatik oluşturulmuşsa)

## ✅ URL'i Bulduktan Sonra

1. **Frontend'i güncelleyin:**
   - `script.js` dosyasında API URL'ini Render.com URL'si ile değiştirin
   - Veya zaten dinamik yapılandırılmışsa, aynı domain'i kullanacak

2. **Test edin:**
   - URL'i tarayıcıda açın
   - API endpoint'lerini test edin: `https://your-url.onrender.com/api/risk`

## 🔧 Frontend'i Render.com URL'si ile Kullanma

Eğer frontend'i ayrı host etmek isterseniz:
- Frontend'i Render.com'da Static Site olarak host edin
- Veya Netlify, Vercel gibi servislerde host edin
- API URL'ini Render.com backend URL'si ile değiştirin

## 💡 İpucu

Render.com'da servis adını değiştirmek isterseniz:
1. Settings > Service Details
2. "Name" alanını değiştirin
3. URL otomatik güncellenir


