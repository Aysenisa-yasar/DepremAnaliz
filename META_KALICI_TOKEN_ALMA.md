# 🔑 Meta WhatsApp Business API - Kalıcı Token Alma

## ⚠️ ÖNEMLİ: Test Token vs Kalıcı Token

- **Test Token:** 24 saatte bir yenilenir, geçici
- **Kalıcı Token:** Süresiz geçerli, production için gerekli

## 📋 Adım Adım: Kalıcı Token Alma

### Adım 1: Meta Developer Console'a Gidin
1. https://developers.facebook.com/apps/ adresine gidin
2. Uygulamanızı seçin (868899732180213)

### Adım 2: System User Oluşturun
1. Sol menüden **"WhatsApp"** > **"API Setup"** seçin
2. **"System Users"** sekmesine gidin
3. **"+ Create System User"** butonuna tıklayın
4. İsim verin (örn: "Deprem Uyarı Sistemi")
5. **"Create"** butonuna tıklayın

### Adım 3: WhatsApp Business API İzinleri Verin
1. Oluşturduğunuz System User'ın yanında **"Assign Assets"** butonuna tıklayın
2. **"WhatsApp Business Account"** seçin
3. İzinleri seçin:
   - ✅ **whatsapp_business_messaging** (mesaj gönderme)
   - ✅ **whatsapp_business_management** (yönetim)
4. **"Save Changes"** butonuna tıklayın

### Adım 4: Kalıcı Token Generate Edin
1. System User'ın yanında **"Generate New Token"** butonuna tıklayın
2. **"WhatsApp Business Account"** seçin
3. İzinleri seçin:
   - ✅ **whatsapp_business_messaging**
   - ✅ **whatsapp_business_management**
4. **"Generate Token"** butonuna tıklayın
5. **TOKEN'I HEMEN KOPYALAYIN!** (bir daha gösterilmez)

### Adım 5: Token'ı Render.com'a Ekleyin
1. Render.com Dashboard → **deprem-izleme-sistemi** servisi
2. **Environment** sekmesine gidin
3. **"+ Add"** butonuna tıklayın
4. **Key:** `META_WHATSAPP_ACCESS_TOKEN`
5. **Value:** Kopyaladığınız kalıcı token'ı yapıştırın
6. **"Save"** butonuna tıklayın
7. **"Save, rebuild, and deploy"** butonuna tıklayın

---

## ✅ Kontrol Listesi

- [ ] System User oluşturuldu
- [ ] WhatsApp Business API izinleri verildi
- [ ] Kalıcı token generate edildi
- [ ] Token kopyalandı (güvenli yerde saklandı)
- [ ] Render.com'a `META_WHATSAPP_ACCESS_TOKEN` eklendi
- [ ] Servis yeniden deploy edildi

---

## 🔒 Güvenlik Notları

1. **Token'ı Güvenli Tutun:**
   - Token'ı asla GitHub'a commit etmeyin
   - Sadece Render.com environment variables'da saklayın
   - Token'ı paylaşmayın

2. **Token Kaybolursa:**
   - Yeni token generate edebilirsiniz
   - Eski token otomatik olarak geçersiz olur

3. **Token Süresi:**
   - Kalıcı token süresiz geçerlidir
   - Ancak manuel olarak revoke edilirse geçersiz olur

---

## 🧪 Token'ı Test Etme

Token'ı ekledikten sonra test edin:

```bash
curl -X GET "https://graph.facebook.com/v22.0/833412653196098?access_token=YOUR_TOKEN"
```

Başarılı cevap alırsanız token çalışıyor demektir.

---

## 📞 Sorun mu Var?

### Token Çalışmıyor?
1. Token'ın doğru kopyalandığından emin olun
2. System User'a doğru izinlerin verildiğini kontrol edin
3. WhatsApp Business Account'ın doğru seçildiğini kontrol edin

### İzin Hatası?
1. System User'a **whatsapp_business_messaging** izninin verildiğinden emin olun
2. WhatsApp Business Account'ın System User'a atandığını kontrol edin

---

## 🎯 Özet

1. Meta Developer Console → System User oluştur
2. WhatsApp Business API izinleri ver
3. Kalıcı token generate et
4. Token'ı Render.com'a ekle
5. Servisi yeniden deploy et

**Kalıcı token süresiz geçerlidir ve production için gereklidir!**
