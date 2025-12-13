# 🚀 GitHub ve Render.com Deploy Rehberi

## 📋 Adım Adım Deploy Süreci

### 1️⃣ GitHub Repository Oluşturma

1. **GitHub'a giriş yapın:** https://github.com
2. **"New repository"** butonuna tıklayın
3. **Repository bilgilerini girin:**
   - Name: `deprem-izleme-sistemi` (veya istediğiniz isim)
   - Description: "AI-powered earthquake monitoring system"
   - Public veya Private seçin
   - **"Initialize with README"** seçeneğini işaretlemeyin (zaten README var)
4. **"Create repository"** butonuna tıklayın

### 2️⃣ Projeyi GitHub'a Yükleme

Terminal/PowerShell'de proje klasöründe:

```bash
# Git'i başlat (eğer daha önce yapmadıysanız)
git init

# Tüm dosyaları ekle
git add .

# İlk commit
git commit -m "Initial commit: AI-powered earthquake monitoring system"

# Branch'i main olarak ayarla
git branch -M main

# GitHub repository'nizi remote olarak ekleyin
# (URL'yi kendi repository'nizle değiştirin)
git remote add origin https://github.com/KULLANICI_ADI/deprem-izleme-sistemi.git

# GitHub'a yükle
git push -u origin main
```

**Not:** İlk kez push yapıyorsanız GitHub kullanıcı adı ve şifre/token isteyebilir.

### 3️⃣ Render.com'da Hesap Oluşturma

1. **Render.com'a gidin:** https://render.com
2. **"Sign Up"** butonuna tıklayın
3. **"Sign up with GitHub"** seçeneğini seçin
4. GitHub hesabınızla giriş yapın
5. Render.com'a erişim izni verin

### 4️⃣ Render.com'da Web Service Oluşturma

1. **Render.com dashboard'a gidin**
2. **"New +"** butonuna tıklayın
3. **"Web Service"** seçeneğini seçin
4. **GitHub repository'nizi seçin:**
   - Repository listesinden `deprem-izleme-sistemi` seçin
   - **"Connect"** butonuna tıklayın

### 5️⃣ Render.com Ayarları

**Basic Settings:**
- **Name:** `deprem-izleme-sistemi`
- **Region:** En yakın bölgeyi seçin (örn: Frankfurt)
- **Branch:** `main`
- **Root Directory:** (boş bırakın)
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

**Advanced Settings:**
- **Auto-Deploy:** `Yes` (otomatik deploy için)

### 6️⃣ Ortam Değişkenlerini Ayarlama

Render.com dashboard'da servisinizde:

1. **"Environment"** sekmesine gidin
2. **"Add Environment Variable"** butonuna tıklayın
3. Şu değişkenleri ekleyin:

```
TWILIO_ACCOUNT_SID = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN = your_auth_token_here
TWILIO_WHATSAPP_NUMBER = whatsapp:+14155238886
PORT = 10000
```

**⚠️ ÖNEMLİ:** 
- Değerleri kendi Twilio bilgilerinizle değiştirin
- Her değişkeni ayrı ayrı ekleyin
- "Save Changes" butonuna tıklayın

### 7️⃣ Deploy Etme

1. **"Create Web Service"** butonuna tıklayın
2. Render.com otomatik olarak:
   - Repository'yi klonlar
   - Bağımlılıkları yükler
   - Uygulamayı deploy eder
3. İlk deploy **5-10 dakika** sürebilir
4. Deploy tamamlandığında URL alacaksınız: `https://deprem-izleme-sistemi.onrender.com`

### 8️⃣ Frontend'i Güncelleme

Render.com'da deploy edildikten sonra, frontend'deki API URL'lerini güncellemeniz gerekebilir.

`script.js` dosyasında API URL'ini kontrol edin:

```javascript
// Eğer localhost kullanıyorsa, Render.com URL'si ile değiştirin
const API_URL = 'https://deprem-izleme-sistemi.onrender.com';
```

Veya dinamik olarak:

```javascript
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:5000' 
    : 'https://deprem-izleme-sistemi.onrender.com';
```

### 9️⃣ Statik Frontend Hosting (Opsiyonel)

Frontend'i ayrı bir statik hosting'de (Netlify, Vercel, GitHub Pages) host edebilirsiniz:

**GitHub Pages için:**
1. Repository Settings > Pages
2. Source: `main` branch, `/` folder
3. Frontend'i `index.html` olarak root'ta tutun

**Netlify için:**
1. Netlify'a giriş yapın
2. "Add new site" > "Import an existing project"
3. GitHub repository'nizi seçin
4. Build settings:
   - Build command: (boş)
   - Publish directory: `/` (veya frontend klasörü)

## 🔧 Sorun Giderme

### Deploy Başarısız Olursa

1. **Build Logs'u kontrol edin:**
   - Render.com dashboard > Logs sekmesi
   - Hata mesajlarını okuyun

2. **Yaygın Hatalar:**
   - **Module not found:** `requirements.txt` eksik paket
   - **Port binding error:** `PORT` environment variable eksik
   - **Twilio error:** Ortam değişkenleri yanlış

### Ortam Değişkenleri Çalışmıyor

1. Render.com dashboard > Environment sekmesi
2. Değişkenlerin doğru olduğundan emin olun
3. **"Save Changes"** butonuna tıklayın
4. **"Manual Deploy"** > **"Deploy latest commit"** yapın

### Frontend API Bağlantı Hatası

1. Browser console'u açın (F12)
2. Network sekmesinde hataları kontrol edin
3. CORS hatası varsa, `app.py`'de CORS ayarlarını kontrol edin
4. API URL'lerinin doğru olduğundan emin olun

## 📝 Önemli Notlar

1. **Ücretsiz Plan:** Render.com ücretsiz planında:
   - Servis 15 dakika kullanılmazsa uyku moduna geçer
   - İlk istekte 30-60 saniye uyanma süresi olabilir
   - Aylık 750 saat ücretsiz

2. **Güvenlik:**
   - `.env` dosyasını `.gitignore`'a ekledik
   - Twilio bilgilerini GitHub'a yüklemeyin
   - Sadece Render.com environment variables kullanın

3. **Güncellemeler:**
   - GitHub'a push yaptığınızda Render.com otomatik deploy eder
   - Manuel deploy için: Dashboard > Manual Deploy

## ✅ Kontrol Listesi

- [ ] GitHub repository oluşturuldu
- [ ] Kod GitHub'a yüklendi
- [ ] Render.com hesabı oluşturuldu
- [ ] Web service oluşturuldu
- [ ] Ortam değişkenleri ayarlandı
- [ ] Deploy başarılı
- [ ] Frontend API URL'leri güncellendi
- [ ] Test edildi

## 🎉 Başarılı Deploy Sonrası

Artık projeniz canlıda! URL'nizi paylaşabilirsiniz:
`https://deprem-izleme-sistemi.onrender.com`

---

**Sorularınız için:** Issue açabilir veya dokümantasyonu kontrol edebilirsiniz.

