# Pull the boot report from the DEEPoS BOOT partition (FAT32) onto the PC.
# The card must be in a card reader; no SSH or UART needed.
param(
    [string]$Out = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Out) { $Out = Join-Path $root "build\device-report" }

$vol = Get-Volume | Where-Object { $_.FileSystemLabel -eq "BOOT" -and $_.DriveLetter } | Select-Object -First 1
if (-not $vol) {
    Write-Host "BOOT partition not found. Insert the card into the reader and check its label:"
    Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, FileSystem, @{n = "GB"; e = { [math]::Round($_.Size / 1GB, 2) } } | Format-Table -AutoSize
    exit 1
}

$src = Join-Path ($vol.DriveLetter + ":") "report"
if (-not (Test-Path $src)) {
    Write-Host "No report on $($vol.DriveLetter): - the system may not have booted yet."
    Write-Host "Contents:"
    Get-ChildItem ($vol.DriveLetter + ":\") | Select-Object Name, Length | Format-Table -AutoSize
    exit 1
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item (Join-Path $src "*") $Out -Force
Write-Host "Report copied to $Out"
Get-ChildItem $Out | Select-Object Name, Length | Format-Table -AutoSize

$boot = Join-Path $Out "boot.txt"
if (Test-Path $boot) {
    Write-Host "--- boot.txt ---"
    Get-Content $boot | Select-Object -First 8
}
$selftest = Join-Path $Out "selftest.txt"
if (Test-Path $selftest) {
    Write-Host "--- selftest.txt ---"
    Get-Content $selftest
}
$temps = Join-Path $Out "temps.txt"
if (Test-Path $temps) {
    Write-Host "--- temps.txt ---"
    Get-Content $temps
}
