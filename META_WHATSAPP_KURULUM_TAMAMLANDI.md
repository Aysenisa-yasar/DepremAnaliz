# ✅ Meta WhatsApp Business API - Kurulum Tamamlandı!

## 🎯 Sistem Durumu

✅ **Kod hazır ve çalışıyor!**
- Meta WhatsApp Business API entegrasyonu tamamlandı
- Session açma (opt-in) sistemi eklendi
- Serbest metin mesaj gönderme hazır
- SMS fallback sistemi aktif
- Deprem tetiklendiğinde otomatik bildirim gönderme aktif

---

## 📋 Yapmanız Gerekenler (SADECE 1 ADIM)

### Render.com'a Token Ekleyin

1. **Render.com Dashboard** → **deprem-izleme-sistemi** servisi
2. **Environment** sekmesi
3. **"+ Add"** butonuna tıklayın
4. **KEY:** `META_WA_TOKEN`
5. **VALUE:** Kalıcı token'ınızı yapıştırın
6. **"Save"** → **"Save, rebuild, and deploy"**

**Bu kadar!** Başka bir şey yapmanıza gerek yok.

---

## ✅ Kontrol Listesi

### Token Ayarları:
- [ ] Kalıcı token alındı (Meta Developer Console)
- [ ] Render.com → `META_WA_TOKEN` eklendi
- [ ] Deploy yapıldı
- [ ] Token test edildi (`/api/test-meta-token`)

### Sistem Hazır:
- [x] Meta WhatsApp API entegrasyonu ✅
- [x] Session açma (opt-in) sistemi ✅
- [x] Serbest metin mesaj gönderme ✅
- [x] SMS fallback ✅
- [x] Deprem tetiklendiğinde otomatik bildirim ✅

---

## 🧪 Test Etme

### 1. Token Testi
```
https://your-backend-url.onrender.com/api/test-meta-token
```

**Başarılı:** `{"success": true, "message": "✅ Token çalışıyor!"}`

### 2. Opt-In Link Testi
```
https://your-backend-url.onrender.com/api/get-opt-in-link
```

**Başarılı:** Opt-in linki döner

### 3. Test Mesajı Gönderme
```bash
POST https://your-backend-url.onrender.com/api/test-meta-whatsapp-send
Body: {"to": "905468964210"}
```

**Not:** Sadece session açılmışsa çalışır!

---

## 🚀 Sistem Nasıl Çalışıyor?

### 1. Kullanıcı Kayıt Olurken:
- Frontend'de "Session Açma Linkini Al" butonuna basar
- Link gösterilir: `https://wa.me/15551679784?text=basla`
- Kullanıcı linke tıklar, WhatsApp'ta "basla" yazar
- ✅ Session açılır (24 saat geçerli)

### 2. Deprem Olduğunda (Otomatik):
- Sistem her 30 saniyede bir depremleri kontrol eder
- M ≥ 5.0 deprem tespit edilirse:
  1. **Meta WhatsApp API** ile serbest metin gönderilir
  2. Başarısız olursa **SMS fallback** devreye girer
  3. Her ikisi de başarısız olursa hata loglanır

### 3. Mesaj İçeriği:
```
🚨 ACİL DEPREM UYARISI 🚨
Büyüklük: M5.2
Yer: İstanbul - Marmara Denizi
Mesafe: 45.3 km (Konumunuza yakın)

📊 HASAR TAHMİNİ:
Seviye: Orta
Skor: 35/100

📍 Deprem Merkezi: [Google Maps Linki]
```

---

## 📊 Kod Yapısı

### Backend (`app.py`):
- ✅ `send_whatsapp_via_meta_api()` - Meta WhatsApp API ile mesaj gönderme
- ✅ `send_sms_via_twilio()` - SMS fallback
- ✅ `send_whatsapp_notification()` - Hybrid sistem (WhatsApp + SMS)
- ✅ `check_for_big_earthquakes()` - Deprem kontrolü ve otomatik bildirim
- ✅ `/api/test-meta-token` - Token test endpoint'i
- ✅ `/api/get-opt-in-link` - Opt-in link endpoint'i
- ✅ `/api/test-meta-whatsapp-send` - Test mesajı endpoint'i

### Frontend (`index.html` + `script.js`):
- ✅ Opt-in link butonu
- ✅ Modal ile talimatlar
- ✅ Otomatik link oluşturma

---

## 🔒 Güvenlik

1. **Token Güvenliği:**
   - Token sadece Render.com environment variables'da
   - GitHub'a commit edilmedi
   - Paylaşılmadı

2. **Session Güvenliği:**
   - Kullanıcı opt-in yapmalı (yasal)
   - 24 saatlik window (Meta kurallarına uygun)

---

## ⚠️ Önemli Notlar

1. **Session Açma:**
   - Kullanıcı mutlaka opt-in linki ile session açmalı
   - Session açılmadan serbest metin gönderilemez
   - 24 saat sonra tekrar session açılabilir

2. **SMS Fallback:**
   - WhatsApp başarısız olursa SMS gönderilir
   - Twilio SMS ayarları gerekli (opsiyonel)

3. **Token Süresi:**
   - Kalıcı token süresiz geçerlidir
   - Ancak manuel revoke edilirse geçersiz olur

---

## 🎉 Özet

**Yapmanız gereken:**
1. ✅ Kalıcı token alın (Meta Developer Console)
2. ✅ Render.com'a `META_WA_TOKEN` ekleyin
3. ✅ Deploy edin
4. ✅ Test edin

**Sistem otomatik çalışacak:**
- ✅ Deprem tespit edilince otomatik bildirim
- ✅ Meta WhatsApp API (öncelikli)
- ✅ SMS fallback (yedek)
- ✅ Her şey hazır!

**Başka bir şey yapmanıza gerek yok!** 🚀
