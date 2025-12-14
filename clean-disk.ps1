# Disk Temizleme Scripti - WhatsApp Servisi için

Write-Host "🧹 Disk temizleme başlatılıyor..." -ForegroundColor Cyan

# npm cache temizle
Write-Host "`n1. npm cache temizleniyor..." -ForegroundColor Yellow
npm cache clean --force
Write-Host "✅ npm cache temizlendi" -ForegroundColor Green

# node_modules sil (yeniden yüklenecek)
if (Test-Path ".\node_modules") {
    Write-Host "`n2. node_modules siliniyor..." -ForegroundColor Yellow
    Remove-Item -Path ".\node_modules" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ node_modules silindi" -ForegroundColor Green
}

# Geçici dosyalar temizle
Write-Host "`n3. Geçici dosyalar temizleniyor..." -ForegroundColor Yellow
$tempPaths = @(
    "$env:TEMP\*",
    "$env:USERPROFILE\AppData\Local\Temp\*"
)

foreach ($path in $tempPaths) {
    try {
        Get-ChildItem -Path $path -ErrorAction SilentlyContinue | 
            Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | 
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        # Hata yok say
    }
}
Write-Host "✅ Geçici dosyalar temizlendi" -ForegroundColor Green

# Disk alanı kontrolü
Write-Host "`n4. Disk alanı kontrol ediliyor..." -ForegroundColor Yellow
$drive = Get-PSDrive C
$freeGB = [math]::Round($drive.Free / 1GB, 2)
$usedGB = [math]::Round($drive.Used / 1GB, 2)

Write-Host "📊 C: Sürücüsü Durumu:" -ForegroundColor Cyan
Write-Host "   Kullanılan: $usedGB GB" -ForegroundColor Yellow
Write-Host "   Boş: $freeGB GB" -ForegroundColor $(if ($freeGB -gt 1) { "Green" } else { "Red" })

if ($freeGB -lt 0.5) {
    Write-Host "`n⚠️ UYARI: Disk alanı çok az! ($freeGB GB)" -ForegroundColor Red
    Write-Host "   En az 500MB boş alan gerekli." -ForegroundColor Yellow
    Write-Host "`n💡 Öneriler:" -ForegroundColor Cyan
    Write-Host "   1. Windows Disk Temizleme aracını kullanın (cleanmgr)" -ForegroundColor White
    Write-Host "   2. Gereksiz dosyaları silin" -ForegroundColor White
    Write-Host "   3. OneDrive'ı senkronize edin" -ForegroundColor White
} else {
    Write-Host "`n✅ Yeterli disk alanı var ($freeGB GB)" -ForegroundColor Green
    Write-Host "`n🚀 Şimdi npm install çalıştırabilirsiniz:" -ForegroundColor Cyan
    Write-Host "   npm install" -ForegroundColor White
}

Write-Host "`n✨ Temizleme tamamlandı!" -ForegroundColor Green
