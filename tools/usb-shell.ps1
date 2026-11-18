# Find the DEEPoS USB console (CDC-ACM gadget) and show how to open it.
# The gadget creates a COM port on the PC; the same cable also gives NCM networking.
param(
    [string]$Port = "",
    [switch]$Interactive
)
$ErrorActionPreference = "Stop"

function Get-DeePosPorts {
    Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.Name -match "COM\d+" -and ($_.Name -match "USB Serial" -or $_.DeviceID -match "VID_1D6B" -or $_.Name -match "Gadget") } |
        Select-Object Name, DeviceID, Manufacturer
}

$ports = @(Get-DeePosPorts)
if (-not $ports) {
    Write-Host "No DEEPoS serial port found. Check:"
    Write-Host "  - the console is booted (not just charging)"
    Write-Host "  - the cable is in the OTG port, not CHARGE"
    Write-Host "  - the gadget bound: the boot report in BOOT/report has no usb errors"
    Write-Host ""
    Write-Host "All serial ports on this PC:"
    Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "COM\d+" } |
        Select-Object Name, Manufacturer | Format-Table -AutoSize
    exit 1
}

$ports | Format-Table -AutoSize

if (-not $Port) {
    if ($ports.Count -eq 1) {
        $m = [regex]::Match($ports[0].Name, "COM\d+")
        if ($m.Success) { $Port = $m.Value }
    }
    else {
        Write-Host "Several candidate ports; pass -Port COMx"
        exit 1
    }
}

Write-Host "Console port: $Port"
Write-Host ""
Write-Host "Open it interactively with one of:"
Write-Host "  plink -serial $Port -sercfg 115200,8,n,1,N"
Write-Host "  putty -serial $Port -sercfg 115200,8,n,1,N"
Write-Host "Login: root (no password - physical access only)."
Write-Host ""
Write-Host "Quick non-interactive check:"
Write-Host "  plink -serial $Port -sercfg 115200,8,n,1,N -batch -m tools/report-commands.sh"
