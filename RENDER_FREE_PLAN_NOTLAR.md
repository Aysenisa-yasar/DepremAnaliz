# 💡 Render.com Ücretsiz Plan - Önemli Notlar

## ✅ Ücretsiz Plan Yeterli!

Bu mesaj sadece bilgilendirme amaçlıdır. Ücretsiz plan ile projenizi deploy edebilirsiniz!

## 📋 Ücretsiz Plan Özellikleri

### ✅ Desteklenen Özellikler:
- ✅ Web Service oluşturma
- ✅ GitHub entegrasyonu
- ✅ Otomatik deploy
- ✅ Environment variables
- ✅ HTTPS sertifikası (otomatik)
- ✅ Custom domain (opsiyonel)
- ✅ 750 saat/ay ücretsiz

### ⚠️ Sınırlamalar (Bu Proje İçin Sorun Değil):
- ❌ 15 dakika kullanılmazsa uyku moduna geçer
- ❌ İlk istekte 30-60 saniye uyanma süresi
- ❌ SSH erişimi yok (gerekli değil)
- ❌ Scaling yok (tek instance yeterli)
- ❌ Persistent disk yok (gerekli değil)

## 🚀 Bu Proje İçin Yeterli

Deprem izleme sistemi için ücretsiz plan yeterlidir çünkü:
- ✅ Flask uygulaması hafif
- ✅ ML modelleri dosya sisteminde (persistent disk gerekmez)
- ✅ Düşük trafik bekleniyor
- ✅ 750 saat/ay yeterli (ayda 31 gün = 744 saat)

## 💡 Uyku Modu İçin Çözümler

### 1. Ücretsiz Keep-Alive Servisleri
- **UptimeRobot:** https://uptimerobot.com (ücretsiz)
- **Cron-job.org:** https://cron-job.org (ücretsiz)
- Her 5-10 dakikada bir ping atarak uyku modunu önler

### 2. Render.com'da Cron Job (Ücretsiz)
Render.com'da "Background Worker" oluşturun:
- **Command:** `curl https://your-app.onrender.com/api/risk`
- **Schedule:** Her 10 dakikada bir

## 🎯 Şimdi Ne Yapmalı?

1. **"Create Web Service" butonuna tıklayın** (ücretsiz plan ile devam edin)
2. Deploy işlemi başlayacak
3. İlk deploy 5-10 dakika sürebilir
4. Deploy tamamlandığında URL alacaksınız: `https://deprem-analiz.onrender.com`

## 💰 Ücretli Plan Gerekli mi?

**Hayır!** Ücretsiz plan yeterli. Ücretli plana geçmek isterseniz:
- **Starter:** $7/ay - Uyku modu yok, daha hızlı
- **Standard:** $25/ay - Daha fazla kaynak

Ama şimdilik ücretsiz plan ile başlayabilirsiniz!

## ✅ Devam Edin

"Create Web Service" butonuna tıklayıp deploy işlemini başlatın. Ücretsiz plan ile sorunsuz çalışacak!


