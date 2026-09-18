<#
  OtoTrend AI Newsroom'u Windows oturumu acildiginda arka planda baslatir.
  Bu betik, ayni anda ikinci bir sunucu acilmasini engeller.
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$logDirectory = Join-Path $projectRoot "logs"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python ortamı bulunamadı: $pythonPath"
}

# Uygulama cevap veriyorsa ikinci kopyayi baslatma. Get-NetTCPConnection
# bazi Windows oturumlarinda mevcut dinleyiciyi gormeyebiliyor; dogrudan
# yerel baglanti denemesi daha guvenilirdir.
$client = [System.Net.Sockets.TcpClient]::new()
try {
    $client.Connect("127.0.0.1", 8765)
    exit 0
}
catch {
    # Port kapaliysa yeni sunucu baslatilacak.
}
finally {
    $client.Dispose()
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8765") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory "server.log") `
    -RedirectStandardError (Join-Path $logDirectory "server-error.log")
