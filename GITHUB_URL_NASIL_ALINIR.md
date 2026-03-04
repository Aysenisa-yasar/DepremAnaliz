# 🔗 GitHub Repository URL'si Nasıl Alınır?

## 📍 Repository Oluşturduktan Sonra

### Yöntem 1: Repository Sayfasından (En Kolay)

1. **GitHub'da repository'nize gidin**
2. **Yeşil "Code" butonuna tıklayın** (sağ üstte, yeşil buton)
3. **"HTTPS" sekmesi seçili olsun**
4. **URL'i kopyalayın** (yanındaki kopyala ikonuna tıklayın)

URL şu formatta olacak:
```
https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git
```

### Yöntem 2: Tarayıcı Adres Çubuğundan

1. **Repository sayfanıza gidin**
2. **Tarayıcı adres çubuğundaki URL'i kopyalayın**
3. **Sonuna `.git` ekleyin**

Örnek:
- Tarayıcıda: `https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi`
- Git için: `https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git`

### Yöntem 3: Repository Ayarlarından

1. **Repository sayfanızda "Settings" sekmesine gidin**
2. **Sol menüden "General" seçin**
3. **"Repository name" altında URL görünecek**

## 📸 Görsel Yerleşim

```
GitHub Repository Sayfası
├── Üst kısım
│   ├── Repository adı: deprem-izleme-sistemi
│   └── [Code ▼] butonu ← BURAYA TIKLAYIN
│       ├── HTTPS (seçili)
│       ├── SSH
│       └── GitHub CLI
│       └── URL: https://github.com/... ← BURADAN KOPYALAYIN
└── ...
```

## ✅ Kontrol

URL şu formatta olmalı:
- ✅ `https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git`
- ❌ `https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi` (`.git` eksik)

## 🔧 PowerShell'de Kullanım

URL'i aldıktan sonra:

```powershell
# Eski remote'u kaldır
git remote remove origin

# Yeni remote'u ekle (URL'i buraya yapıştırın)
git remote add origin https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git

# Kontrol edin
git remote -v

# Push yapın
git push -u origin main
```

## 💡 İpucu

Repository henüz oluşturmadıysanız:
1. https://github.com → "+" → "New repository"
2. Repository oluşturun
3. Oluşturulduktan sonra sayfada URL görünecek

