#!/usr/bin/env python3
# Twilio Kurulum ve Test Scripti

import os
from twilio.rest import Client

def setup_twilio():
    """Twilio ayarlarını yapılandırır"""
    print("="*60)
    print("TWILIO WHATSAPP KURULUM REHBERI")
    print("="*60)
    
    print("\n[1/5] Twilio Hesabi Olusturma:")
    print("  1. https://www.twilio.com adresine gidin")
    print("  2. Ucretsiz hesap olusturun")
    print("  3. Telefon numaranizi dogrulayin")
    
    print("\n[2/5] WhatsApp Sandbox Aktiflestirme:")
    print("  1. Twilio Console'da 'Messaging' > 'Try it out' > 'Send a WhatsApp message'")
    print("  2. WhatsApp Sandbox'i aktiflestirin")
    print("  3. Sandbox numarasini not edin (ornek: whatsapp:+14155238886)")
    
    print("\n[3/5] Kimlik Bilgilerini Alin:")
    print("  1. Twilio Console'da 'Account' > 'Account Info'")
    print("  2. Account SID ve Auth Token'i kopyalayin")
    
    print("\n[4/5] Ortam Degiskenlerini Ayarlayin:")
    print("  Windows PowerShell icin:")
    print("  $env:TWILIO_ACCOUNT_SID='your_account_sid'")
    print("  $env:TWILIO_AUTH_TOKEN='your_auth_token'")
    print("  $env:TWILIO_WHATSAPP_NUMBER='whatsapp:+14155238886'")
    
    print("\n[5/5] WhatsApp Sandbox'a Katilin:")
    print("  1. Twilio Console'da WhatsApp Sandbox sayfasina gidin")
    print("  2. Gosterilen kodu not edin (ornek: 'join abc-xyz')")
    print("  3. Bu kodu WhatsApp'tan Twilio numarasina gonderin")
    
    print("\n" + "="*60)
    print("AYARLARI GIRIN:")
    print("="*60)
    
    account_sid = input("\nTwilio Account SID: ").strip()
    auth_token = input("Twilio Auth Token: ").strip()
    whatsapp_number = input("Twilio WhatsApp Number (whatsapp:+14155238886): ").strip()
    
    if not account_sid or not auth_token or not whatsapp_number:
        print("\n[ERROR] Tum alanlar doldurulmali!")
        return False
    
    # Test bağlantısı
    print("\n[TEST] Twilio baglantisi test ediliyor...")
    try:
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        print(f"[OK] Baglanti basarili! Hesap: {account.friendly_name}")
        
        # Ortam değişkenlerini ayarla
        print("\n[AYAR] Ortam degiskenleri ayarlaniyor...")
        os.environ['TWILIO_ACCOUNT_SID'] = account_sid
        os.environ['TWILIO_AUTH_TOKEN'] = auth_token
        os.environ['TWILIO_WHATSAPP_NUMBER'] = whatsapp_number
        
        print("[OK] Ortam degiskenleri ayarlandi!")
        
        # Test mesajı gönder
        print("\n[TEST] Test mesaji gonderiliyor...")
        test_number = input("Test icin WhatsApp numaranizi girin (+90XXXXXXXXXX): ").strip()
        
        if test_number:
            if not test_number.startswith('+'):
                test_number = '+' + test_number
            
            try:
                message = client.messages.create(
                    body="Test mesaji: Twilio entegrasyonu basarili!",
                    from_=whatsapp_number,
                    to=f"whatsapp:{test_number}"
                )
                print(f"[OK] Test mesaji gonderildi! SID: {message.sid}")
                print("\n[NOT] Eger mesaj gelmediyse:")
                print("  1. WhatsApp Sandbox'a katildiginizdan emin olun")
                print("  2. Numara formatini kontrol edin (+90XXXXXXXXXX)")
                print("  3. Twilio Console'da mesaj durumunu kontrol edin")
            except Exception as e:
                print(f"[ERROR] Test mesaji gonderilemedi: {e}")
                print("\n[NOT] Muhtemel nedenler:")
                print("  1. WhatsApp Sandbox'a katilmamissiniz")
                print("  2. Numara format hatali")
                print("  3. Twilio hesabinizda yeterli kredi yok")
        
        # .env dosyası oluştur (opsiyonel)
        create_env = input("\n.env dosyasi olusturulsun mu? (e/h): ").strip().lower()
        if create_env == 'e':
            env_content = f"""# Twilio Ayarlari
TWILIO_ACCOUNT_SID={account_sid}
TWILIO_AUTH_TOKEN={auth_token}
TWILIO_WHATSAPP_NUMBER={whatsapp_number}
"""
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            print("[OK] .env dosyasi olusturuldu!")
            print("[NOT] .env dosyasini .gitignore'a eklemeyi unutmayin!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Baglanti hatasi: {e}")
        print("\n[NOT] Kontrol edin:")
        print("  1. Account SID ve Auth Token dogru mu?")
        print("  2. Internet baglantisi var mi?")
        print("  3. Twilio hesabiniz aktif mi?")
        return False

if __name__ == "__main__":
    setup_twilio()

