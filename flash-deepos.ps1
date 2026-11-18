# Elevated flasher for DEEPoS: writes build/deepos-r36s-v20.img to the SD card.
# Run through Start-Process -Verb RunAs (or flash-deepos.cmd) so \\.\PhysicalDriveN is writable.
param(
    [int]$Disk = 2,
    [string]$Image = "build/deepos-r36s-v20.img",
    [string]$Sha256 = "",
    [string]$Python = ""
)
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $root "build\flash.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
function Log([string]$m) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $line
}

if (-not $Python) {
    $candidate = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $candidate) { $Python = $candidate }
    else {
        $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}

Set-Content -Path $log -Value "" -Encoding UTF8
Log "start: disk=$Disk image=$Image"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("Administrator")
Log ("admin=" + $isAdmin)
if (-not $isAdmin) { Log "STOP: not elevated, run flash-deepos.cmd and accept the UAC prompt"; exit 2 }
Log ("python=" + $Python)

if (-not $Sha256) {
    $rel = Join-Path $root "docs\RELEASE.md"
    if (Test-Path $rel) {
        $m = Select-String -Path $rel -Pattern 'image sha256: `([0-9a-f]{64})`' | Select-Object -First 1
        if ($m) { $Sha256 = $m.Matches[0].Groups[1].Value }
    }
}
Log ("expected sha256=" + $(if ($Sha256) { $Sha256 } else { "unknown" }))
if (-not $Python -or -not (Test-Path $Python)) { Log "STOP: python interpreter not found"; exit 1 }

$d = Get-Disk -Number $Disk
Log ("target: " + $d.FriendlyName + " size=" + $d.Size + " bus=" + $d.BusType + " style=" + $d.PartitionStyle)
if ($d.FriendlyName -notmatch "STORAGE DEVICE") { Log "STOP: unexpected disk name"; exit 1 }
if ($d.Size -ne 53745811456) { Log "STOP: unexpected disk size"; exit 1 }

$img = Join-Path $root $Image
if (-not (Test-Path $img)) { Log "STOP: image not found: $img"; exit 1 }
Log ("image bytes=" + (Get-Item $img).Length)

# Drop drive letters/access paths so nothing keeps the card open.
Get-Partition -DiskNumber $Disk -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.DriveLetter) {
        Log ("removing access path " + $_.DriveLetter)
        Remove-PartitionAccessPath -DiskNumber $Disk -PartitionNumber $_.PartitionNumber `
            -AccessPath ($_.DriveLetter + ":") -ErrorAction SilentlyContinue
    }
}

Log "writing..."
try {
    $out = & $Python (Join-Path $root "tools\dpflash.py") --image $img `
        --target ("\\.\PhysicalDrive" + $Disk) --expect-sha256 $Sha256 2>&1
    $code = $LASTEXITCODE
    foreach ($line in @($out)) { Log ("  " + $line) }
    Log "dpflash exit=$code"
} catch {
    Log ("dpflash threw: " + $_.Exception.Message)
}

$after = Get-Disk -Number $Disk
Log ("after: style=" + $after.PartitionStyle + " partitions=" + $after.NumberOfPartitions)
Get-Partition -DiskNumber $Disk -ErrorAction SilentlyContinue |
    ForEach-Object { Log ("  part " + $_.PartitionNumber + " " + $_.Size + " offset=" + $_.Offset) }
Log "DONE"
