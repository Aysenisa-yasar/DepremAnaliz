#!/usr/bin/env python3
# API ile Kullanıcı Kayıt Kontrolü
# Production (Render.com) sunucusundaki veriyi kontrol eder

import requests
import json

# Kontrol edilecek numara
TARGET_NUMBER = "+905456246352"

# Backend API URL'i (Render.com veya localhost)
# Render.com URL'inizi buraya yazın
BACKEND_URL = "https://depremanaliz.onrender.com"  # Bu URL'i kendi Render.com URL'inizle değiştirin

# Veya localhost için:
# BACKEND_URL = "http://localhost:5000"

print("="*60)
print(f"KULLANICI KAYIT KONTROLU (API): {TARGET_NUMBER}")
print("="*60)
print(f"\nBackend URL: {BACKEND_URL}")

# API isteği
payload = {
    "number": TARGET_NUMBER
}

print(f"\nAPI'ye istek gonderiliyor...")
print(f"Numara: {TARGET_NUMBER}")

try:
    response = requests.post(
        f"{BACKEND_URL}/api/check-user",
        json=payload,
        timeout=10,
        headers={
            'Content-Type': 'application/json'
        }
    )
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        if result.get('registered'):
            print(f"\n[OK] KAYIT BULUNDU!")
            print("="*60)
            print(f"Numara: {result.get('number')}")
            data = result.get('data', {})
            print(f"Koordinatlar: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}")
            print(f"Istanbul Bildirimi: {data.get('istanbul_alert', False)}")
            print(f"Kayit Zamani: {data.get('registered_at', 'N/A')}")
            print("="*60)
            print("\nBu numara sisteme kayitli ve bildirimler aktif!")
        else:
            print(f"\n[NOT] KAYIT BULUNAMADI")
            print(f"\nBu numara sisteme kayitli degil.")
            print(f"\nKayit yapmak icin:")
            print(f"   1. Web sitesine gidin")
            print(f"   2. 'Acil Durum WhatsApp Bildirim Ayarlari' bolumune gidin")
            print(f"   3. Konumunuzu belirleyin")
            print(f"   4. WhatsApp numaranizi girin: {TARGET_NUMBER}")
            print(f"   5. 'Ayarlari Kaydet' butonuna tiklayin")
    else:
        print(f"\n[ERROR] API hatasi: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print(f"\n[ERROR] Backend'e baglanilamadi!")
    print(f"URL: {BACKEND_URL}")
    print("\nKontrol edin:")
    print("  1. Backend calisiyor mu? (Render.com'da servis aktif mi?)")
    print("  2. URL dogru mu?")
    print("  3. Backend uyku modunda olabilir (10-15 saniye bekleyin)")
    
except requests.exceptions.Timeout:
    print(f"\n[ERROR] Timeout! Backend yanit vermedi.")
    print("Render.com ucretsiz plan'da yavas olabilir.")
    
except Exception as e:
    print(f"\n[ERROR] Hata: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
