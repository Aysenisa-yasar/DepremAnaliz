# 📱 MESAJ GÖNDERİM SİSTEMİ - DETAYLI AÇIKLAMA

## 📍 NUMARALAR NEREYE KAYDEDİLİYOR?

### Dosya: `user_alerts.json`
- **Konum**: Backend sunucusunda (Render.com'da)
- **Format**: JSON dosyası
- **İçerik**: Her numara için konum bilgisi (lat, lon) ve kayıt tarihi

### Örnek `user_alerts.json` içeriği:
```json
{
  "+905551234567": {
    "lat": 41.0082,
    "lon": 28.9784,
    "registered_at": "2024-01-20T14:30:00"
  },
  "+905559876543": {
    "lat": 39.9334,
    "lon": 32.8597,
    "registered_at": "2024-01-20T15:00:00",
    "istanbul_alert": true
  }
}
```

---

## 🚨 MESAJ GÖNDERİM MANTIĞI

### 1. DEPREM ÖNCESİ ERKEN UYARI (Proaktif)

#### İstanbul Erken Uyarı Sistemi:
- **Ne zaman gönderilir**: Deprem olmadan ÖNCE, anomali tespit edildiğinde
- **Koşul**: İstanbul için KRİTİK, YÜKSEK veya ORTA seviye uyarı
- **Kontrol sıklığı**: Her 30 saniyede bir
- **Mesaj içeriği**:
  ```
  🚨 İSTANBUL ERKEN UYARI SİSTEMİ 🚨
  
  ⚠️ DEPREM ÖNCESİ UYARI ⚠️
  
  Uyarı Seviyesi: KRİTİK
  Uyarı Skoru: 0.85/1.0
  Tahmini Süre: 0-24 saat içinde
  Mesaj: Anormal aktivite tespit edildi
  
  ⚠️ LÜTFEN HAZIRLIKLI OLUN:
  • Acil durum çantanızı hazırlayın
  • Güvenli yerleri belirleyin
  • Aile acil durum planınızı gözden geçirin
  ```

#### Tüm Türkiye Erken Uyarı:
- **Ne zaman gönderilir**: Herhangi bir şehir için M ≥ 5.0 deprem riski tespit edildiğinde
- **Koşul**: KRİTİK, YÜKSEK veya ORTA seviye + M ≥ 5.0 tahmini
- **Kontrol sıklığı**: Her 30 saniyede bir
- **Mesaj içeriği**:
  ```
  🚨 ANKARA ERKEN UYARI SİSTEMİ 🚨
  
  ⚠️ M ≥ 5.0 DEPREM RİSKİ TESPİT EDİLDİ ⚠️
  
  Şehir: Ankara
  Uyarı Seviyesi: YÜKSEK
  Tahmini Büyüklük: M5.2
  Tahmini Süre: 24-72 saat içinde
  ```

---

### 2. DEPREM SONRASI ACİL UYARI (Reaktif)

#### M ≥ 5.0 Deprem Bildirimi:
- **Ne zaman gönderilir**: M ≥ 5.0 deprem olduğunda
- **Koşul**: 
  - Deprem büyüklüğü M ≥ 5.0
  - Kullanıcının konumu deprem merkezine 150 km içinde
- **Kontrol sıklığı**: Her 30 saniyede bir
- **Mesaj içeriği**:
  ```
  🚨 ACİL DEPREM UYARISI 🚨
  Büyüklük: M5.5
  Yer: İstanbul - Marmara Denizi
  Saat: 2024-01-20 14:30:00
  Derinlik: 10 km
  Mesafe: 45.3 km (Konumunuza yakın)
  
  📊 HASAR TAHMİNİ:
  Seviye: Orta
  Skor: 65/100
  Açıklama: Orta seviye hasar bekleniyor
  
  📍 Deprem Merkezi: [Google Maps Linki]
  📍 Sizin Konumunuz: [Google Maps Linki]
  
  ⚠️ Lütfen güvende kalın ve acil durum planınızı uygulayın!
  ```

---

## 🔄 SİSTEM NASIL ÇALIŞIYOR?

### Arka Plan Thread'leri:

1. **`check_for_big_earthquakes()` Thread'i**:
   - Her 30 saniyede bir çalışır
   - Kandilli API'den güncel deprem verilerini çeker
   - İki kontrol yapar:
     a) **Erken Uyarı Kontrolü**: Deprem olmadan önce anomali tespiti
     b) **Acil Uyarı Kontrolü**: M ≥ 5.0 deprem oldu mu?

2. **Mesaj Gönderim Süreci**:
   ```
   Her 30 saniyede:
   1. Kandilli'den güncel veri çek
   2. Erken uyarı kontrolü yap
      - İstanbul için anomali var mı?
      - Tüm Türkiye için M ≥ 5.0 riski var mı?
   3. Acil uyarı kontrolü yap
      - M ≥ 5.0 deprem oldu mu?
      - Kullanıcılar 150 km içinde mi?
   4. Mesaj gönder:
      - Meta WhatsApp API dene
      - Başarısız olursa SMS fallback
   ```

---

## 📊 MESAJ GÖNDERİM DETAYLARI

### Konum Kontrolü:
- **Mesafe hesaplama**: Haversine formülü ile
- **150 km kuralı**: Kullanıcının konumu deprem merkezine 150 km içindeyse mesaj gönderilir
- **Şehir bazlı**: En yakın şehir bulunur ve o şehir için uyarı kontrol edilir

### Spam Önleme:
- **1 saat kuralı**: Aynı uyarı seviyesi için 1 saat içinde tekrar mesaj gönderilmez
- **Son deprem kontrolü**: Aynı deprem için 30 dakika içinde tekrar mesaj gönderilmez

### Mesaj Gönderim Yöntemleri:
1. **Meta WhatsApp API** (Öncelikli):
   - Session açılmışsa serbest metin gönderir
   - Session yoksa SMS fallback

2. **Twilio SMS** (Fallback):
   - Meta WhatsApp başarısız olursa SMS gönderir
   - Ücretsiz Twilio hesabı ile sınırlı (günlük limit)

---

## ✅ MESAJ GÖNDERİMİNİN GARANTİSİ

### Evet, mesajlar gerçekten gönderiliyor:

1. **Deprem Öncesi**:
   - ✅ İstanbul için anomali tespit edildiğinde
   - ✅ Tüm Türkiye için M ≥ 5.0 riski tespit edildiğinde
   - ✅ Her 30 saniyede bir kontrol yapılıyor

2. **Deprem Sonrası**:
   - ✅ M ≥ 5.0 deprem olduğunda
   - ✅ Kullanıcı 150 km içindeyse
   - ✅ Her 30 saniyede bir kontrol yapılıyor

3. **Konum Bilgisi**:
   - ✅ Deprem merkezi Google Maps linki gönderiliyor
   - ✅ Kullanıcı konumu Google Maps linki gönderiliyor
   - ✅ Mesafe bilgisi gönderiliyor

---

## 🔍 KONTROL ETMEK İÇİN

### Backend Logs'da göreceğiniz mesajlar:

**Erken Uyarı**:
```
🚨 İSTANBUL ERKEN UYARI: KRİTİK - Anormal aktivite tespit edildi
✅ İstanbul erken uyarı bildirimi gönderildi: +905551234567
```

**Acil Uyarı**:
```
!!! YENİ BÜYÜK DEPREM TESPİT EDİLDİ: M5.5 @ (41.0082, 28.9784)
✅ Büyük deprem bildirimi gönderildi: +905551234567
```

**Hata Durumu**:
```
[ERROR] İstanbul bildirimi gönderilemedi (+905551234567): SESSION_REQUIRED
[INFO] WhatsApp session açılmamış, SMS fallback deneniyor...
✅ SMS bildirimi gönderildi: +905551234567
```

---

## ⚠️ ÖNEMLİ NOTLAR

1. **Meta WhatsApp Session**: Serbest metin mesajlar için önce session açmanız gerekiyor (opt-in linki ile)

2. **Twilio Sandbox**: Ücretsiz Twilio hesabı kullanıyorsanız, numaranızı sandbox'a eklemeniz gerekiyor

3. **SMS Fallback**: WhatsApp gönderilemezse otomatik olarak SMS gönderilir

4. **Rate Limits**: 
   - Twilio ücretsiz: Günlük mesaj limiti var
   - Meta WhatsApp: Session açılmışsa limit yok (24 saat içinde)

---

## 📝 ÖZET

✅ **Numaralar**: `user_alerts.json` dosyasına kaydediliyor
✅ **Deprem Öncesi**: Erken uyarı mesajları gönderiliyor
✅ **Deprem Sonrası**: M ≥ 5.0 depremlerde 150 km içindeyse mesaj gönderiliyor
✅ **Konum Bilgisi**: Google Maps linkleri ile gönderiliyor
✅ **Sistem**: Her 30 saniyede bir kontrol yapıyor

**Sistem tam otomatik çalışıyor ve mesajlar gerçekten gönderiliyor!** 🚀
