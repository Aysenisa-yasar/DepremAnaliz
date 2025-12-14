# 🔧 GitHub Pages 404 Hatası Çözümü

## ❌ Sorun
404 hatası alıyorsunuz: "There isn't a GitHub Pages site here."

## ✅ Çözüm Adımları

### 1. GitHub Pages'i Aktifleştirin

1. **Repository sayfanıza gidin:**
   https://github.com/Aysenisa-yasar/DepremAnaliz

2. **"Settings" sekmesine tıklayın** (üst menüde)

3. **Sol menüden "Pages" seçeneğine tıklayın**

4. **"Source" bölümünde:**
   - **"Deploy from a branch"** seçin
   - **Branch:** `main` seçin
   - **Folder:** `/ (root)` seçin
   - **"Save"** butonuna tıklayın

### 2. Deploy Durumunu Kontrol Edin

1. **"Pages" sayfasında** deploy durumunu göreceksiniz
2. **Yeşil tik** göründüğünde site hazırdır
3. **URL görünecek:** `https://aysenisa-yasar.github.io/DepremAnaliz/`

### 3. Bekleme Süresi

- İlk deploy **1-5 dakika** sürebilir
- Deploy tamamlandığında yeşil tik görünecek
- Sayfayı yenileyin (F5)

### 4. Hala 404 Alıyorsanız

#### Kontrol 1: index.html Dosyası Root'ta mı?
- `index.html` dosyası repository'nin root klasöründe olmalı
- `/DepremAnaliz/index.html` konumunda olmalı

#### Kontrol 2: Branch Doğru mu?
- Pages ayarlarında `main` branch seçili olmalı
- Başka branch seçiliyse `main`'e değiştirin

#### Kontrol 3: Deploy Durumu
- Settings > Pages sayfasında deploy durumunu kontrol edin
- Hata varsa kırmızı işaret görünecek
- Logları kontrol edin

## 🔄 Hızlı Çözüm

Eğer hala çalışmıyorsa:

1. **Settings > Pages** sayfasına gidin
2. **"Source"** ayarını değiştirin (başka bir seçenek seçin)
3. **"Save"** butonuna tıklayın
4. Tekrar **"main"** branch'ini seçin
5. **"Save"** butonuna tekrar tıklayın
6. 2-3 dakika bekleyin

## ✅ Başarılı Olursa

Site şu adresten açılacak:
```
https://aysenisa-yasar.github.io/DepremAnaliz/
```

## 📝 Not

- GitHub Pages sadece **statik dosyalar** için çalışır (HTML, CSS, JS)
- Backend (Flask) Render.com'da çalışıyor
- Frontend GitHub Pages'de, Backend Render.com'da


