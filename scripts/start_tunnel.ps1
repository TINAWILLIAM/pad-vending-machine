# start_tunnel.ps1 – Start a Cloudflare Tunnel to expose the Angular frontend

param(
    [int]$Port = 4200,
    [string]$GenerateQR = "yes"
)

Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "  Pad Vending Machine – Cloudflare Tunnel " -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Magenta

# Check cloudflared is installed
if (-not (Get-Command "cloudflared" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ cloudflared not found." -ForegroundColor Red
    Write-Host "   Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor Yellow
    exit 1
}

Write-Host "🌐 Starting Cloudflare Tunnel → http://localhost:$Port …" -ForegroundColor Green

# Run tunnel in background and capture the URL
$job = Start-Job -ScriptBlock {
    param($port)
    cloudflared tunnel --url "http://localhost:$port" 2>&1
} -ArgumentList $Port

# Wait for URL to appear
$tunnelUrl = $null
$timeout = 30
$elapsed = 0

while (-not $tunnelUrl -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    $output = Receive-Job $job -Keep
    $match = $output | Select-String -Pattern "https://[a-z0-9\-]+\.trycloudflare\.com" | Select-Object -Last 1
    if ($match) {
        $tunnelUrl = $match.Matches[0].Value
    }
}

if (-not $tunnelUrl) {
    Write-Host "❌ Failed to get tunnel URL after ${timeout}s." -ForegroundColor Red
    Stop-Job $job
    exit 1
}

Write-Host ""
Write-Host "✅ Tunnel URL: $tunnelUrl" -ForegroundColor Green
Write-Host ""

# Generate QR code
if ($GenerateQR -eq "yes") {
    Write-Host "📱 Generating QR code …" -ForegroundColor Cyan
    & python scripts/generate_qr.py --url $tunnelUrl
}

Write-Host "Press Ctrl+C to stop the tunnel." -ForegroundColor Yellow
Wait-Job $job
