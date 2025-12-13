# Twilio Ortam Degiskenlerini Ayarlama Scripti
# PowerShell'de calistirin: .\setup_twilio_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TWILIO ORTAM DEGISKENLERI AYARLANIYOR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Account SID (ekrandan gordugunuz)
$accountSid = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Buraya kendi Account SID'nizi girin

# Auth Token'i girin (Twilio Console'dan alin)
$authToken = Read-Host "Twilio Auth Token'i girin (gizli, Show butonuna tiklayin)"

# WhatsApp Sandbox numarasi (genelde bu)
$whatsappNumber = Read-Host "WhatsApp Sandbox numarasi (ornek: whatsapp:+14155238886)"

# Eger bos birakilirsa varsayilan degeri kullan
if ([string]::IsNullOrWhiteSpace($whatsappNumber)) {
    $whatsappNumber = "whatsapp:+14155238886"
}

# Ortam degiskenlerini ayarla (gecici - bu terminal icin)
$env:TWILIO_ACCOUNT_SID = $accountSid
$env:TWILIO_AUTH_TOKEN = $authToken
$env:TWILIO_WHATSAPP_NUMBER = $whatsappNumber

Write-Host ""
Write-Host "[OK] Ortam degiskenleri ayarlandi!" -ForegroundColor Green
Write-Host ""
Write-Host "Account SID: $accountSid" -ForegroundColor Yellow
Write-Host "Auth Token: $($authToken.Substring(0, [Math]::Min(10, $authToken.Length)))..." -ForegroundColor Yellow
Write-Host "WhatsApp Number: $whatsappNumber" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOT: Bu ayarlar sadece bu terminal oturumu icin gecerli." -ForegroundColor Cyan
Write-Host "Kalici yapmak icin sistem degiskeni olarak ayarlayin." -ForegroundColor Cyan
Write-Host ""

# Kalici yapmak ister misiniz?
$makePermanent = Read-Host "Kalici olarak ayarlamak ister misiniz? (e/h)"

if ($makePermanent -eq "e" -or $makePermanent -eq "E") {
    [System.Environment]::SetEnvironmentVariable('TWILIO_ACCOUNT_SID', $accountSid, 'User')
    [System.Environment]::SetEnvironmentVariable('TWILIO_AUTH_TOKEN', $authToken, 'User')
    [System.Environment]::SetEnvironmentVariable('TWILIO_WHATSAPP_NUMBER', $whatsappNumber, 'User')
    Write-Host "[OK] Kalici olarak ayarlandi! Yeni terminal acmaniz gerekebilir." -ForegroundColor Green
}

Write-Host ""
Write-Host "Test etmek icin: python app.py" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

