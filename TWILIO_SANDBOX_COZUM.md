# 🔧 Twilio WhatsApp Sandbox Sorunu Çözümü

## ❌ Sorun
Başka bir numara girince Twilio'dan bildirim gitmiyor, sadece kendi numaranıza geliyor.

## 🔍 Neden?
Twilio WhatsApp **Sandbox modunda** çalışıyor. Sandbox modunda sadece **sandbox'a kayıtlı numaralara** mesaj gönderebilirsiniz.

## ✅ Çözüm 1: Sandbox'a Numara Ekleme (ÜCRETSİZ - Hızlı)

### Adımlar:
1. **Twilio Console'a gidin:** https://console.twilio.com
2. **Messaging** > **Try it out** > **Send a WhatsApp message** sayfasına gidin
3. **WhatsApp Sandbox** bölümünde **"Join code"** kısmını bulun
   - Örnek: `join abc-xyz` veya `join example-code`
4. **WhatsApp'ı açın** ve Twilio numarasına (genelde `+1 415 523 8886`) bu kodu gönderin
   - Örnek mesaj: `join abc-xyz`
5. **Onay mesajı** gelecek: "You're all set! ..."
6. Artık o numaraya mesaj gönderebilirsiniz!

### ⚠️ Önemli:
- Her numara için ayrı ayrı sandbox'a eklenmesi gerekir
- Sandbox modu **ücretsizdir** ama sınırlıdır
- Sadece kayıtlı numaralara mesaj gönderebilirsiniz

---

## ✅ Çözüm 2: Production Moduna Geçme (ÜCRETLİ - Sınırsız)

### Adımlar:
1. **Twilio Console'a gidin:** https://console.twilio.com
2. **Messaging** > **Settings** > **WhatsApp Senders** sayfasına gidin
3. **"Request WhatsApp Sender"** butonuna tıklayın
4. **WhatsApp Business API onayı** için başvuru yapın
5. Twilio onayladıktan sonra production numaranızı alın
6. Ortam değişkenlerini güncelleyin:
   ```
   TWILIO_WHATSAPP_NUMBER=whatsapp:+YENI_PRODUCTION_NUMARASI
   ```

### ⚠️ Önemli:
- Production modu **ücretlidir** (mesaj başına ücret)
- **Sınırsız** numaraya mesaj gönderebilirsiniz
- Onay süreci birkaç gün sürebilir

---

## 🚀 Hızlı Test

### Sandbox'a Numara Ekleme Testi:
1. Twilio Console'dan "join code" alın
2. WhatsApp'tan Twilio numarasına (`+1 415 523 8886`) "join <code>" gönderin
3. Onay mesajı gelince, uygulamadan o numarayı girin
4. Bildirim gelmeli!

---

## 📝 Notlar

- **Sandbox modu:** Ücretsiz, sınırlı (sadece kayıtlı numaralar)
- **Production modu:** Ücretli, sınırsız (tüm numaralar)
- **Öneri:** Test için sandbox, gerçek kullanım için production

---

## 🔗 İlgili Dosyalar

- `TWILIO_KURULUM.md` - Detaylı kurulum rehberi
- `TWILIO_ADIMLAR.md` - Adım adım kurulum
- `app.py` - `send_whatsapp_notification()` fonksiyonu

