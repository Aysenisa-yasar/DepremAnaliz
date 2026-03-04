#!/usr/bin/env python3
# Kullanıcı Kayıt Kontrol Scripti
# Belirtilen numaranın sisteme kayıtlı olup olmadığını kontrol eder

import os
import json

# Kontrol edilecek numara
TARGET_NUMBER = "+905456246352"

print("="*60)
print(f"KULLANICI KAYIT KONTROLU: {TARGET_NUMBER}")
print("="*60)

# Kullanıcı verileri dosyası
USER_DATA_FILE = 'user_alerts.json'

print(f"\nDosya yolu: {os.path.abspath(USER_DATA_FILE)}")

# Dosya var mı kontrol et
if not os.path.exists(USER_DATA_FILE):
    print(f"\n[NOT] Dosya bulunamadi: {USER_DATA_FILE}")
    print("\nOlası nedenler:")
    print("  1. Henuz hic kullanici kaydi yapilmamis")
    print("  2. Dosya Render.com sunucusunda (production'da)")
    print("  3. Farkli bir dizinde olabilir")
    print("\nNOT: Bu script yerel dosyayi kontrol eder.")
    print("   Production (Render.com) icin backend API'yi kullanin.")
    exit(1)

# Dosyayı oku
try:
    with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
        user_alerts = json.load(f)
    
    print(f"\n[OK] Dosya bulundu ve okundu.")
    print(f"Toplam kayitli kullanici sayisi: {len(user_alerts)}")
    
    # Numara formatlarını kontrol et (farklı formatlar olabilir)
    number_variants = [
        TARGET_NUMBER,                    # +905456246352
        TARGET_NUMBER.replace('+', ''),   # 905456246352
        TARGET_NUMBER.replace('+90', '0'), # 05456246352
        '0' + TARGET_NUMBER.replace('+90', '') # 05456246352 (alternatif)
    ]
    
    print(f"\nKontrol ediliyor...")
    print(f"   Aradigimiz numara: {TARGET_NUMBER}")
    
    # Kayıtlı numaraları listele
    print(f"\nKayitli numaralar:")
    found = False
    
    for number, data in user_alerts.items():
        print(f"   - {number}")
        
        # Eşleşme kontrolü
        if number in number_variants or number_variants[0] in number:
            found = True
            print(f"\n[OK] KAYIT BULUNDU!")
            print(f"="*60)
            print(f"Numara: {number}")
            print(f"Koordinatlar: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}")
            print(f"Istanbul Bildirimi: {data.get('istanbul_alert', False)}")
            
            # Şehir bilgisi varsa
            if 'city' in data:
                print(f"Sehir: {data.get('city', 'N/A')}")
            
            # Kayıt zamanı varsa
            if 'registered_at' in data:
                print(f"Kayit Zamani: {data.get('registered_at', 'N/A')}")
            
            print(f"="*60)
            break
    
    if not found:
        print(f"\n[NOT] KAYIT BULUNAMADI")
        print(f"\nBu numara sisteme kayitli degil.")
        print(f"\nKayit yapmak icin:")
        print(f"   1. Web sitesine gidin")
        print(f"   2. 'Acil Durum WhatsApp Bildirim Ayarlari' bolumune gidin")
        print(f"   3. Konumunuzu belirleyin")
        print(f"   4. WhatsApp numaranizi girin: {TARGET_NUMBER}")
        print(f"   5. 'Ayarlari Kaydet' butonuna tiklayin")
        
except json.JSONDecodeError as e:
    print(f"\n[ERROR] JSON dosyasi okunamadi: {e}")
    print("Dosya bozuk olabilir.")
    
except Exception as e:
    print(f"\n[ERROR] Hata olustu: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("\nNOT: Bu script sadece yerel dosyayi kontrol eder.")
print("   Production (Render.com) sunucusundaki veriyi gormek icin")
print("   backend API'yi kullanmaniz gerekir.")
