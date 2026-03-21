Write-Host "[setup] Python araniyor..."

$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3.11"
}

if (-not $pythonCmd) {
    throw "Python bulunamadi. Python 3.11 kurup tekrar deneyin."
}

Write-Host "[setup] Pip guncelleniyor..."
Invoke-Expression "$pythonCmd -m pip install --upgrade pip"

Write-Host "[setup] Torch kuruluyor..."
Invoke-Expression "$pythonCmd -m pip install torch"

Write-Host "[setup] Torch Geometric kuruluyor..."
Invoke-Expression "$pythonCmd -m pip install torch-geometric"

Write-Host "[setup] Kurulum tamamlandi."
