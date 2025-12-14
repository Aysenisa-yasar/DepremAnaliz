# 💾 Disk Alanı Sorunu Çözümü

## 🔴 Sorun
`npm install` sırasında Puppeteer Chromium indirilemiyor - disk alanı yetersiz.

## ✅ Çözümler

### 1. npm Cache Temizle (Hızlı)

```powershell
npm cache clean --force
```

### 2. Disk Alanı Temizle

#### Geçici Dosyaları Temizle:
```powershell
# Windows Temp klasörü
Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue

# npm cache
npm cache clean --force

# node_modules sil (yeniden yükleyeceğiz)
Remove-Item -Path ".\node_modules" -Recurse -Force -ErrorAction SilentlyContinue
```

#### Disk Temizleme Aracı:
1. Windows + R tuşlarına bas
2. `cleanmgr` yaz ve Enter
3. C: sürücüsünü seç
4. "Geçici dosyalar" ve "İndirilenler" seç
5. Temizle

### 3. Puppeteer'ı Skip Et (Geçici)

Eğer sadece test etmek istiyorsanız:

```powershell
$env:PUPPETEER_SKIP_DOWNLOAD="true"
npm install
```

**NOT:** Bu durumda WhatsApp servisi çalışmayacak, sadece diğer paketler yüklenecek.

### 4. Render.com'da Çalıştır (Önerilen)

Yerel kurulum yerine Render.com'da çalıştırabilirsiniz:

1. Render.com'da yeni **Web Service** oluştur
2. Repository'yi bağla
3. Build: `npm install`
4. Start: `node whatsapp-service.js`
5. Render.com'da disk alanı sorunu olmayacak

### 5. Alternatif: Daha Hafif WhatsApp Kütüphanesi

Eğer Puppeteer çok yer kaplıyorsa, alternatif kütüphaneler:

- `@wppconnect-team/wppconnect` - Daha hafif
- `venom-bot` - Alternatif WhatsApp bot

Ama `whatsapp-web.js` en stabil ve popüler olanı.

## 🎯 Önerilen Adımlar

1. **npm cache temizle**
2. **Disk alanı temizle** (en az 500MB boş alan gerekli)
3. **Tekrar npm install dene**

```powershell
npm cache clean --force
npm install
```

## 📊 Gerekli Disk Alanı

- Puppeteer Chromium: ~300MB
- node_modules: ~200MB
- Toplam: ~500MB boş alan gerekli

## ⚠️ Önemli

WhatsApp Web.js için Puppeteer **zorunlu**. Chromium olmadan WhatsApp'a bağlanamaz.
