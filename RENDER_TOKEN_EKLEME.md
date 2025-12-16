# 🔑 Render.com'a Meta WhatsApp Token Ekleme - Adım Adım

## ✅ Hızlı Adımlar

### 1. Render.com Dashboard'a Gidin
1. https://render.com adresine gidin
2. Giriş yapın
3. Dashboard'a gidin

### 2. Flask Backend Servisine Gidin
1. **"deprem-izleme-sistemi"** servisini bulun
2. Servis adına **tıklayın** (mavi link)

### 3. Environment Sekmesine Gidin
1. Üstteki sekmelerden **"Environment"** sekmesine tıklayın
2. Veya sol menüden **"Environment"** seçeneğine tıklayın

### 4. Token'ı Ekleyin
1. **"+ Add"** butonuna tıklayın
2. **KEY:** `META_WA_TOKEN`
3. **VALUE:** Kalıcı token'ınızı yapıştırın (örn: `EAAXXXXX...`)
4. **"Save"** butonuna tıklayın

### 5. Deploy Edin
1. **"Save, rebuild, and deploy"** butonuna tıklayın (sağ alt köşede)
2. 2-3 dakika bekleyin
3. Deploy tamamlanacak

---

## 🧪 Token'ı Test Edin

### Yöntem 1: Backend Test Endpoint'i
Deploy tamamlandıktan sonra:
```
https://your-backend-url.onrender.com/api/test-meta-token
```

**Başarılı cevap:**
```json
{
  "success": true,
  "message": "✅ Token çalışıyor!",
  "phone_number_id": "833412653196098"
}
```

### Yöntem 2: Tarayıcıdan Direkt Test
```
https://graph.facebook.com/v22.0/833412653196098?access_token=YOUR_TOKEN
```

**Başarılı:** JSON döner (phone number bilgileri)
**Hata:** OAuth hatası döner

---

## ✅ Kontrol Listesi

- [ ] Kalıcı token alındı (Meta Developer Console'dan)
- [ ] Render.com → Environment → `META_WA_TOKEN` eklendi
- [ ] Token değeri doğru kopyalandı (tam token, eksik değil)
- [ ] "Save, rebuild, and deploy" yapıldı
- [ ] Deploy başarılı oldu
- [ ] Token test edildi (`/api/test-meta-token`)

---

## ⚠️ Önemli Notlar

1. **Token İsmi:**
   - ✅ Doğru: `META_WA_TOKEN` (ChatGPT formatı)
   - ✅ Alternatif: `META_WHATSAPP_ACCESS_TOKEN` (eski format, hala çalışır)
   - ❌ Yanlış: `META_WA_ACCESS_TOKEN` veya diğerleri

2. **Token Formatı:**
   - Token uzun bir string (100+ karakter)
   - Başında `EAA` ile başlar
   - Tırnak işareti kullanmayın
   - Boşluk olmamalı

3. **Güvenlik:**
   - Token'ı asla GitHub'a commit etmeyin
   - Sadece Render.com environment variables'da saklayın
   - Token'ı paylaşmayın

---

## 🔧 Sorun Giderme

### Token Çalışmıyor?
1. Token'ın tam kopyalandığından emin olun
2. Environment variable isminin `META_WA_TOKEN` olduğunu kontrol edin
3. Deploy'ın tamamlandığını kontrol edin
4. Logs sekmesinden hata mesajlarını kontrol edin

### OAuth Hatası?
1. Token'ın geçerli olduğundan emin olun
2. System User'a doğru izinlerin verildiğini kontrol edin
3. WhatsApp Business Account'ın doğru seçildiğini kontrol edin

---

## 🎯 Özet

1. Render.com → **deprem-izleme-sistemi** servisi
2. **Environment** sekmesi
3. **"+ Add"** → **KEY:** `META_WA_TOKEN` → **VALUE:** Token'ınız
4. **"Save"** → **"Save, rebuild, and deploy"**
5. Test edin: `/api/test-meta-token`

**Token eklendikten sonra sistem otomatik çalışacak!**
