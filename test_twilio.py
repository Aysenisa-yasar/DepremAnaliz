#!/usr/bin/env python3
# Twilio Test Scripti

import os
from twilio.rest import Client

# Ortam değişkenlerini kontrol et
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
whatsapp_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

print("="*60)
print("TWILIO WHATSAPP TEST")
print("="*60)
print(f"\nAccount SID: {account_sid}")
print(f"Auth Token: {auth_token[:10] + '...' if auth_token else 'AYARLANMADI'}")
print(f"WhatsApp Number: {whatsapp_number}")

if not account_sid or not auth_token or not whatsapp_number:
    print("\n[ERROR] Twilio ayarlari eksik!")
    print("Lutfen ortam degiskenlerini ayarlayin.")
    exit(1)

# Test numarası al
test_number = input("\nTest icin WhatsApp numaranizi girin (+90XXXXXXXXXX): ").strip()

if not test_number:
    print("[ERROR] Numara gerekli!")
    exit(1)

# Numara formatını düzelt
if not test_number.startswith('+'):
    test_number = '+' + test_number.lstrip('0')

print(f"\nTest numarasi: {test_number}")
print("Mesaj gonderiliyor...")

try:
    client = Client(account_sid, auth_token)
    
    message_body = """Test Mesaji: Deprem Izleme Sistemi

Bu bir test mesajidir. Twilio entegrasyonu basarili!

Eger bu mesaji aldiysaniz, sistem calisiyor demektir.
150 km icinde 5+ deprem oldugunda otomatik bildirim alacaksiniz."""
    
    message = client.messages.create(
        body=message_body,
        from_=whatsapp_number,
        to=f"whatsapp:{test_number}"
    )
    
    print(f"\n[OK] Mesaj gonderildi!")
    print(f"Message SID: {message.sid}")
    print(f"Status: {message.status}")
    print("\nWhatsApp'tan mesaji kontrol edin.")
    print("\nEger mesaj gelmediyse:")
    print("  1. WhatsApp Sandbox'a katildiginizdan emin olun")
    print("  2. Twilio Console > Monitor > Logs > Messaging kontrol edin")
    print("  3. Numara formatini kontrol edin (+90 ile baslamali)")
    
except Exception as e:
    error_msg = str(e)
    print(f"\n[ERROR] Mesaj gonderilemedi: {error_msg}")
    
    if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
        print("\n[NOT] Muhtemel nedenler:")
        print("  - Account SID veya Auth Token hatali")
        print("  - WhatsApp Sandbox'a katilmamissiniz")
        print("  - Numara format hatali")
    elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
        print("\n[NOT] Yetki sorunu:")
        print("  - Auth Token yanlis olabilir")
        print("  - Hesap aktif degil olabilir")
    elif "not a valid" in error_msg.lower():
        print("\n[NOT] Numara format hatasi:")
        print("  - Numara ulke kodu ile baslamali (+90)")
        print("  - WhatsApp Sandbox'a kayitli numara olmali")

print("\n" + "="*60)

