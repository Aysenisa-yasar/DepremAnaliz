# Disk Alani Sorunu - Hizli Cozum

## Sorun
npm install sirasinda Puppeteer Chromium indirilemiyor - disk alani yetersiz.

## Hizli Cozumler

### 1. npm Cache Temizle (Yapildi)
```powershell
npm cache clean --force
```

### 2. Manuel Disk Temizleme

#### Windows Disk Temizleme:
1. Windows + R tuslarina basin
2. `cleanmgr` yazin ve Enter
3. C: surucusunu secin
4. "Gecici dosyalar" ve "Indirilenler" secin
5. Temizle butonuna basin

#### Geçici Dosyaları Sil:
```powershell
# Temp klasorunu temizle
Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue

# npm cache (zaten yapildi)
npm cache clean --force
```

### 3. Render.com'da Calistir (ONERILEN)

Yerel kurulum yerine Render.com'da calistirabilirsiniz:

1. Render.com'da yeni **Web Service** olustur
2. Repository'yi bagla
3. Build Command: `npm install`
4. Start Command: `node whatsapp-service.js`
5. Render.com'da disk alani sorunu olmayacak

### 4. Alternatif: Puppeteer Olmadan Test

Eger sadece kod test etmek istiyorsaniz:

```powershell
$env:PUPPETEER_SKIP_DOWNLOAD="true"
npm install
```

**NOT:** Bu durumda WhatsApp servisi calismayacak, sadece diger paketler yuklenecek.

## Gerekli Disk Alani

- Puppeteer Chromium: ~300MB
- node_modules: ~200MB
- Toplam: ~500MB bos alan gerekli

## En Iyi Cozum

**Render.com'da calistirin!** Yerel disk alani sorunu olmayacak ve production'da calisacak.
