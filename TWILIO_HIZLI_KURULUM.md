# 🚀 Twilio WhatsApp Hızlı Kurulum Rehberi

## 📋 Adım Adım Kurulum

### 1️⃣ Twilio Hesabı Oluşturma
1. **https://www.twilio.com** adresine gidin
2. **"Sign Up"** butonuna tıklayın
3. Ücretsiz hesap oluşturun (telefon numaranızı doğrulamanız gerekecek)
4. Email doğrulaması yapın

### 2️⃣ WhatsApp Sandbox'ı Aktifleştirme
1. Twilio Console'a giriş yapın: **https://console.twilio.com**
2. Sol menüden **"Messaging"** > **"Try it out"** > **"Send a WhatsApp message"** seçin
3. **"Get started with WhatsApp"** butonuna tıklayın
4. WhatsApp Sandbox'ı aktifleştirin
5. **Sandbox numaranızı not edin** (örn: `whatsapp:+14155238886`)

### 3️⃣ Kimlik Bilgilerini Alın
1. Twilio Console'da sol üst köşeden **"Account"** > **"Account Info"** seçin
2. Şu bilgileri kopyalayın:
   - **Account SID** (AC ile başlar)
   - **Auth Token** (gizli, göster butonuna tıklayın)

### 4️⃣ WhatsApp Sandbox'a Katılın
1. Twilio Console'da **"Messaging"** > **"Try it out"** > **"Send a WhatsApp message"** sayfasına gidin
2. **"Join code"** kısmında gösterilen kodu not edin (örn: `join abc-xyz`)
3. WhatsApp'ı açın ve Twilio numarasına (örn: +1 415 523 8886) bu kodu gönderin
   - Örnek: `join abc-xyz` mesajını gönderin
4. Onay mesajı gelecek: **"You're all set! ..."**

### 5️⃣ Ortam Değişkenlerini Ayarlayın

#### Windows PowerShell (Geçici - Terminal Kapatılınca Sıfırlanır):
```powershell
$env:TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TWILIO_AUTH_TOKEN="your_auth_token_here"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"
```

#### Windows PowerShell (Kalıcı - Sistem Değişkeni):
```powershell
[System.Environment]::SetEnvironmentVariable('TWILIO_ACCOUNT_SID', 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'User')
[System.Environment]::SetEnvironmentVariable('TWILIO_AUTH_TOKEN', 'your_auth_token_here', 'User')
[System.Environment]::SetEnvironmentVariable('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886', 'User')
```

#### .env Dosyası Oluşturma (Önerilen):
Proje klasöründe `.env` dosyası oluşturun:
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

**ÖNEMLİ:** `.env` dosyasını `.gitignore`'a ekleyin!

### 6️⃣ Test Edin
```bash
python twilio_setup.py
```

veya uygulamayı çalıştırıp frontend'den test edin.

## ✅ Test Senaryosu

1. Uygulamayı başlatın: `python app.py`
2. Frontend'i açın: `index.html`
3. Konumunuzu belirleyin
4. WhatsApp numaranızı girin: `+905551234567` (ülke kodu ile)
5. "Ayarları Kaydet" butonuna tıklayın
6. WhatsApp'tan onay mesajı gelmeli

## 🔧 Sorun Giderme

### Mesaj Gelmiyor?
- ✅ WhatsApp Sandbox'a katıldınız mı? (`join <kod>` mesajını gönderdiniz mi?)
- ✅ Numara formatı doğru mu? (`+90` ile başlamalı)
- ✅ Twilio Console'da mesaj durumunu kontrol edin: **"Monitor"** > **"Logs"** > **"Messaging"**

### Hata Mesajları
- **"not found"** → Account SID veya Auth Token hatalı
- **"unauthorized"** → Auth Token yanlış veya hesap aktif değil
- **"not a valid number"** → Numara formatı hatalı veya Sandbox'a kayıtlı değil

### Ortam Değişkenleri Çalışmıyor?
1. Terminal'i kapatıp yeniden açın
2. `.env` dosyası kullanıyorsanız, `python-dotenv` paketini yükleyin:
   ```bash
   pip install python-dotenv
   ```
3. `app.py` dosyasının başına ekleyin:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

## 📱 Production Kullanımı

Sandbox sadece test içindir. Gerçek kullanım için:
1. Twilio'dan **WhatsApp Business API** onayı alın
2. Onaylandıktan sonra gerçek WhatsApp Business numarası kullanabilirsiniz
3. Ücretli plana geçmeniz gerekebilir

## 💰 Maliyet

- **Sandbox:** Ücretsiz (sadece kayıtlı numaralara)
- **Production:** Mesaj başına ücret (ülkeye göre değişir)

## 📞 Destek

- Twilio Dokümantasyon: https://www.twilio.com/docs/whatsapp
- Twilio Console: https://console.twilio.com
- Twilio Support: https://support.twilio.com

