# Twilio WhatsApp Entegrasyonu Kurulum Kılavuzu

## Twilio Hesabı Oluşturma

1. **Twilio Hesabı Oluşturun:**
   - https://www.twilio.com adresine gidin
   - Ücretsiz hesap oluşturun

2. **WhatsApp Sandbox'ı Aktifleştirin:**
   - Twilio Console'da "Messaging" > "Try it out" > "Send a WhatsApp message" bölümüne gidin
   - WhatsApp Sandbox'ı aktifleştirin
   - Sandbox numarasını not edin (örn: `whatsapp:+14155238886`)

3. **Kimlik Bilgilerini Alın:**
   - Twilio Console'da "Account" > "Account Info" bölümünden:
     - `Account SID`
     - `Auth Token`
   - Bu bilgileri not edin

## Ortam Değişkenlerini Ayarlama

### Yerel Geliştirme (Windows PowerShell):
```powershell
$env:TWILIO_ACCOUNT_SID="your_account_sid_here"
$env:TWILIO_AUTH_TOKEN="your_auth_token_here"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"  # Sandbox numaranız
```

### Render.com veya Diğer Cloud Platformlar:
- Platform'unuzun ortam değişkenleri bölümüne ekleyin:
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_WHATSAPP_NUMBER`

## WhatsApp Sandbox'a Katılma

1. Twilio Console'da WhatsApp Sandbox sayfasına gidin
2. Sandbox'a katılmak için gösterilen kodu WhatsApp'tan Twilio numarasına gönderin
   - Örnek: `join <kod>` mesajını gönderin

## Test Etme

1. Uygulamayı çalıştırın
2. Konumunuzu belirleyin
3. WhatsApp numaranızı girin (ülke kodu ile, örn: `+905xxxxxxxxx`)
4. Ayarları kaydedin
5. Onay mesajı WhatsApp'tan gelmelidir

## Önemli Notlar

- **Sandbox Modu:** Ücretsiz Twilio hesabı ile sadece sandbox numarasına kayıtlı numaralara mesaj gönderebilirsiniz
- **Production:** Gerçek kullanım için Twilio'dan WhatsApp Business API onayı almanız gerekir
- **Maliyet:** Sandbox ücretsizdir, ancak production kullanımı ücretlidir

## Sorun Giderme

- **Mesaj gelmiyor:** Sandbox'a katıldığınızdan emin olun
- **Hata mesajı:** Ortam değişkenlerinin doğru ayarlandığından emin olun
- **Numara formatı:** Telefon numarası mutlaka ülke kodu ile başlamalı (örn: `+90`)

