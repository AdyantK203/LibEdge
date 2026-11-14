$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "backend")
if (-not $env:MONGODB_URI) {
    $secret = Read-Host "Paste your complete MongoDB URI" -AsSecureString
    $env:MONGODB_URI = [System.Net.NetworkCredential]::new("", $secret).Password
    Remove-Variable secret
}
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "libedge_yolo_detections"
$env:MONGODB_POLL_SECONDS = "2"
$env:SIMULATE = "0"
if (-not $env:NODE_KEY) { $env:NODE_KEY = [guid]::NewGuid().ToString("N") }
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
