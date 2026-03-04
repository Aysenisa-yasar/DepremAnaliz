# 🔑 Twilio Auth Token Nasıl Bulunur?

## 📍 Adım Adım Rehber

### 1. Twilio Console'a Giriş Yapın
- https://console.twilio.com adresine gidin
- Giriş yapın

### 2. Account Info Sayfasına Gidin
- Sol üst köşede **"Account"** menüsüne tıklayın
- **"Account Info"** seçeneğine tıklayın
- VEYA direkt şu linke gidin: https://console.twilio.com/us1/account/settings

### 3. Auth Token'ı Bulun
- Sayfada aşağı kaydırın
- **"Auth Token"** bölümünü bulun
- Token gizli olarak gösterilir: `••••••••••••••••`
- Yanında **"Show"** butonu var

### 4. Token'ı Gösterin ve Kopyalayın
- **"Show"** butonuna tıklayın
- Token görünecek (uzun bir string)
- **Kopyala** butonuna tıklayın veya manuel olarak kopyalayın
- ⚠️ **ÖNEMLİ:** Token bir daha gösterilmez! Not alın!

## 📸 Görsel Yerleşim

```
Twilio Console
├── Sol Üst Köşe
│   └── Account ▼
│       └── Account Info
│           ├── Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx ✅
│           ├── Auth Token: •••••••••••••••• [Show] ← BURAYA TIKLAYIN
│           └── ...
```

## ⚠️ Önemli Notlar

1. **Token Gizlidir:** İlk kez gösterildiğinde kopyalayın, bir daha gösterilmez
2. **Güvenlik:** Token'ı kimseyle paylaşmayın
3. **Yeniden Oluşturma:** Token'ı unutursanız "Regenerate" butonuyla yeni token oluşturabilirsiniz

## 🔄 Token'ı Yeniden Oluşturma

Eğer token'ı kaybettiyseniz:
1. Auth Token bölümünde **"Regenerate"** butonuna tıklayın
2. Yeni token oluşturulacak
3. Eski token artık çalışmayacak

## ✅ Token'ı Aldıktan Sonra

PowerShell'de şu komutu çalıştırın:
```powershell
$env:TWILIO_AUTH_TOKEN="buraya_kopyaladiginiz_token"
```

