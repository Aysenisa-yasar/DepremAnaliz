# PowerShell Ortam Değişkenleri - Doğru Kullanım

## ❌ Yanlış (Bash/Linux Syntax)
```powershell
NODE_VERSION=18.17.0
PORT=3001
```

## ✅ Doğru (PowerShell Syntax)
```powershell
$env:NODE_VERSION="18.17.0"
$env:PORT="3001"
$env:USE_WHATSAPP_WEB="true"
$env:WHATSAPP_WEB_SERVICE_URL="https://whatsapp-service.onrender.com"
```

## 📝 Render.com'da Ortam Değişkenleri

**Render.com'da ortam değişkenleri Web UI'dan ayarlanır, terminal'den değil!**

### Flask Backend (deprem-izleme-sistemi) için:

1. Render.com Dashboard'a gidin
2. **deprem-izleme-sistemi** servisini seçin
3. **Environment** sekmesine gidin
4. **"Add Environment Variable"** butonuna tıklayın
5. Şu değişkenleri ekleyin:

```
Key: USE_WHATSAPP_WEB
Value: true

Key: WHATSAPP_WEB_SERVICE_URL
Value: https://whatsapp-service.onrender.com
```

**NOT:** `whatsapp-service.onrender.com` yerine kendi WhatsApp servisinizin URL'ini yazın.

### WhatsApp Servisi (whatsapp-service) için:

1. Render.com Dashboard'a gidin
2. **whatsapp-service** servisini seçin
3. **Environment** sekmesine gidin
4. **"Add Environment Variable"** butonuna tıklayın
5. Şu değişkenleri ekleyin:

```
Key: NODE_VERSION
Value: 18.17.0

Key: PORT
Value: 3001
```

## 🔍 QR Kod Sürekli Yenileniyor - Normal!

QR kod sürekli yenileniyorsa bu **normal** bir durumdur:

- WhatsApp bağlanana kadar QR kod her 20 saniyede bir yenilenir
- Bu WhatsApp Web.js'in güvenlik özelliğidir
- QR kodu okuttuğunuzda bağlantı kurulur ve yenilenme durur

## ✅ QR Kod ile Bağlanma Adımları

1. WhatsApp servisi deploy olduktan sonra:
   - Frontend'inize gidin (GitHub Pages)
   - "📱 WhatsApp QR Kod ile Bağlan" butonuna tıklayın
   - QR kod görünecek (sürekli yenilenebilir, bu normal)

2. WhatsApp'tan QR kodu okutun:
   - WhatsApp → Ayarlar → Bağlı Cihazlar → Cihaz Bağla
   - QR kodu okutun
   - **Hızlı olun!** QR kod 20 saniyede bir yenilenir

3. Bağlantı başarılı olunca:
   - Terminal'de `[WhatsApp] ✅ Bağlantı başarılı!` mesajı görünecek
   - QR kod yenilenmeyi durduracak
   - Frontend'de "✅ WhatsApp Bağlı" yazacak

## 🐛 Sorun Giderme

### QR Kod Görünmüyor
- WhatsApp servisi deploy edilmiş mi kontrol edin
- Render.com'da servis çalışıyor mu kontrol edin
- Browser console'da hata var mı bakın

### QR Kod Sürekli Yenileniyor
- **Bu normal!** WhatsApp bağlanana kadar devam eder
- QR kodu hızlı okutun (20 saniye içinde)

### Bağlantı Kurulamıyor
- WhatsApp'ı telefonunuzda açın
- İnternet bağlantınızı kontrol edin
- QR kodun süresi dolmadan okutun
