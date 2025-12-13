# 🚀 Twilio Kurulum - Adım Adım

## ✅ Şu Anki Durum
- ✅ Twilio hesabı oluşturuldu
- ✅ Account SID: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- ⏳ Auth Token alınacak
- ⏳ WhatsApp Sandbox ayarlanacak

## 📝 Yapılacaklar

### 1. Auth Token'ı Alın
1. Twilio Console'da aynı sayfada **"Auth Token"** bölümünü bulun
2. **"Show"** butonuna tıklayın
3. Token'ı kopyalayın (bir daha gösterilmez!)

### 2. WhatsApp Sandbox'ı Aktifleştirin
1. Sol menüden: **"Messaging"** > **"Try it out"** > **"Send a WhatsApp message"**
2. **"Get started with WhatsApp"** butonuna tıklayın
3. Sandbox numarasını not edin (genelde: `whatsapp:+14155238886`)

### 3. WhatsApp Sandbox'a Katılın
1. Sandbox sayfasında **"Join code"** kısmını bulun (örn: `join abc-xyz`)
2. WhatsApp'ı açın
3. Twilio numarasına (örn: +1 415 523 8886) bu kodu gönderin
   - Örnek mesaj: `join abc-xyz`
4. Onay mesajı gelecek

### 4. Ortam Değişkenlerini Ayarlayın

#### Seçenek A: PowerShell Script ile (Önerilen)
```powershell
.\setup_twilio_env.ps1
```

#### Seçenek B: Manuel PowerShell Komutları
```powershell
$env:TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TWILIO_AUTH_TOKEN="your_auth_token_here"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"
```

#### Seçenek C: Kalıcı Sistem Değişkeni
```powershell
[System.Environment]::SetEnvironmentVariable('TWILIO_ACCOUNT_SID', 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'User')
[System.Environment]::SetEnvironmentVariable('TWILIO_AUTH_TOKEN', 'your_auth_token_here', 'User')
[System.Environment]::SetEnvironmentVariable('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886', 'User')
```

### 5. Test Edin
```bash
python app.py
```

Frontend'den:
1. Konumunuzu belirleyin
2. WhatsApp numaranızı girin: `+905551234567` (ülke kodu ile)
3. "Ayarları Kaydet" butonuna tıklayın
4. WhatsApp'tan onay mesajı gelmeli

## 🔍 Kontrol Listesi
- [ ] Auth Token alındı
- [ ] WhatsApp Sandbox aktifleştirildi
- [ ] Sandbox numarası not edildi
- [ ] WhatsApp Sandbox'a katıldınız (join kodu gönderildi)
- [ ] Ortam değişkenleri ayarlandı
- [ ] Test mesajı gönderildi

## ❓ Sorun mu var?

### Mesaj gelmiyor?
- WhatsApp Sandbox'a katıldınız mı? (`join <kod>` gönderdiniz mi?)
- Numara formatı doğru mu? (`+90` ile başlamalı)
- Twilio Console'da "Monitor" > "Logs" > "Messaging" bölümünü kontrol edin

### Hata mesajı?
- Ortam değişkenleri doğru mu? `echo $env:TWILIO_ACCOUNT_SID` ile kontrol edin
- Terminal'i kapatıp yeniden açtınız mı? (kalıcı ayarlar için)

