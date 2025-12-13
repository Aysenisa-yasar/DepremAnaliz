#!/usr/bin/env python3
# Twilio API Test - Frontend'den test için hazır

import requests
import json

BASE_URL = "http://localhost:5000"

print("="*60)
print("TWILIO WHATSAPP API TEST")
print("="*60)

# Test verileri
test_data = {
    "number": "+905551234567",  # Bu numarayı kendi numaranızla değiştirin
    "lat": 41.0082,  # İstanbul koordinatları
    "lon": 28.9784
}

print(f"\nTest verileri:")
print(f"  Numara: {test_data['number']}")
print(f"  Konum: ({test_data['lat']}, {test_data['lon']})")

print("\n[NOT] Bu numarayi kendi WhatsApp numaranizla degistirin!")
print("Numara format: +90XXXXXXXXXX (ulke kodu ile)")
print("\nAPI'ye istek gonderiliyor...")

try:
    response = requests.post(
        f"{BASE_URL}/api/set-alert",
        json=test_data,
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"[OK] Basarili!")
        print(f"Sonuc: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print("\nWhatsApp'tan onay mesaji gelmeli!")
        print("Eger mesaj gelmediyse:")
        print("  1. WhatsApp Sandbox'a katildiginizdan emin olun")
        print("  2. Numara formatini kontrol edin")
        print("  3. Twilio Console > Monitor > Logs kontrol edin")
    else:
        print(f"[ERROR] Hata: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n[ERROR] Backend calismiyor!")
    print("Once 'python app.py' ile backend'i baslatin.")
except Exception as e:
    print(f"\n[ERROR] Hata: {e}")

print("\n" + "="*60)

