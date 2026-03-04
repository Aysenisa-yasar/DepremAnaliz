# 🚀 GitHub'a Yükleme Komutları

## İlk Kez Yükleme

```bash
# Git'i başlat
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

## Güncelleme Yaparken

```bash
# Değişiklikleri ekle
git add .

# Commit yap
git commit -m "Açıklayıcı mesaj buraya"

# GitHub'a yükle
git push
```

## Önemli Notlar

1. **İlk push'ta GitHub kullanıcı adı ve şifre/token isteyebilir**
2. **Personal Access Token kullanmanız önerilir** (şifre yerine)
3. **.gitignore dosyası hassas bilgileri korur**

## GitHub Personal Access Token Oluşturma

1. GitHub > Settings > Developer settings > Personal access tokens > Tokens (classic)
2. "Generate new token" butonuna tıklayın
3. İzinleri seçin (repo)
4. Token'ı kopyalayın ve güvenli bir yerde saklayın
5. Push yaparken şifre yerine bu token'ı kullanın

