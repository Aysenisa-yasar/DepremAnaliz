# 🚀 GitHub Repository Oluşturma - Hızlı Rehber

## ✅ Şu Anki Durum
- ✅ Git init yapıldı
- ✅ Dosyalar commit edildi
- ❌ Repository GitHub'da henüz oluşturulmadı

## 📝 Adım Adım

### 1. GitHub'da Repository Oluşturun

1. **GitHub'a gidin:** https://github.com
2. **Sağ üst köşede "+" butonuna tıklayın**
3. **"New repository" seçin**
4. **Repository bilgilerini girin:**
   - **Repository name:** `deprem-izleme-sistemi` (veya istediğiniz isim)
   - **Description:** "AI-powered earthquake monitoring system"
   - **Public** veya **Private** seçin
   - ⚠️ **"Initialize with README"** seçeneğini İŞARETLEMEYİN (zaten README var)
   - ⚠️ **"Add .gitignore"** seçeneğini İŞARETLEMEYİN (zaten var)
5. **"Create repository" butonuna tıklayın**

### 2. Repository URL'ini Kopyalayın

Repository oluşturulduktan sonra GitHub size URL gösterecek:
```
https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git
```

Bu URL'i kopyalayın!

### 3. PowerShell'de Remote'u Güncelleyin

PowerShell'de şu komutları çalıştırın (URL'i kendi repository'nizle değiştirin):

```powershell
# Eski remote'u kaldır
git remote remove origin

# Yeni remote'u ekle (URL'i kendi repository'nizle değiştirin)
git remote add origin https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git

# Push yap
git push -u origin main
```

### 4. Authentication

İlk push'ta GitHub kullanıcı adı ve şifre/token isteyecek:
- **Username:** GitHub kullanıcı adınız
- **Password:** GitHub şifreniz VEYA Personal Access Token

**Önerilen:** Personal Access Token kullanın (daha güvenli)

## 🔑 Personal Access Token Oluşturma

1. GitHub > **Settings** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**
2. **"Generate new token"** > **"Generate new token (classic)"**
3. **Note:** "Deprem Izleme Sistemi" (açıklama)
4. **Expiration:** İstediğiniz süre (90 gün önerilir)
5. **Scopes:** `repo` seçeneğini işaretleyin
6. **"Generate token"** butonuna tıklayın
7. **Token'ı kopyalayın** (bir daha gösterilmez!)

Push yaparken şifre yerine bu token'ı kullanın.

## ✅ Tam Komut Seti

```powershell
# 1. Eski remote'u kaldır
git remote remove origin

# 2. Yeni remote'u ekle (URL'i değiştirin!)
git remote add origin https://github.com/KULLANICI_ADINIZ/deprem-izleme-sistemi.git

# 3. Push yap
git push -u origin main
```

## 🎉 Başarılı Olursa

Şu mesajı göreceksiniz:
```
Enumerating objects: 25, done.
Counting objects: 100% (25/25), done.
Writing objects: 100% (25/25), done.
To https://github.com/...
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

## ❓ Sorun mu var?

### "Repository not found" hatası
- Repository'yi GitHub'da oluşturdunuz mu?
- URL doğru mu? (kullanıcı adınızı kontrol edin)

### "Authentication failed" hatası
- Kullanıcı adı doğru mu?
- Personal Access Token kullanıyorsanız, token doğru mu?
- Token'ın `repo` yetkisi var mı?

### "Permission denied" hatası
- Repository'ye erişim yetkiniz var mı?
- Repository private ise, erişim izniniz var mı?

