# Elevated Windows entry point. Invoke with flash-deepos.cmd or from an elevated PowerShell.
param(
    [int]$Disk = 0,
    [string]$Image = "",
    [string]$Sha256 = "",
    [string]$Python = "",
    [switch]$Fresh
)

function Test-FlashAdministrator {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-FlashDisk([int]$Number) {
    $candidates = @(Get-Disk -ErrorAction Stop | Where-Object {
        $_.FriendlyName -match 'STORAGE DEVICE' -and $_.Size -eq 53745811456 -and
        $_.BusType -in @('USB', 'SD', 'MMC') -and $_.IsBoot -eq $false -and
        $_.IsSystem -eq $false -and $_.IsOffline -eq $false -and $_.IsReadOnly -eq $false
    })
    if ($candidates.Count -ne 1) { throw "Expected one matching SD card, found $($candidates.Count)" }
    $candidate = $candidates[0]
    if ($Number -ne 0 -and $candidate.Number -ne $Number) { throw "Matching SD card is disk $($candidate.Number), requested disk $Number" }
    if (-not $candidate.Path) { throw "Windows did not report a device path for disk $Number" }
    if ($candidate.LogicalSectorSize -ne 512) { throw "Disk $Number must have 512-byte logical sectors" }
    return $candidate
}

function Invoke-DeepOSFlash {
    param([int]$Disk = 0, [string]$Image = '',
          [string]$Sha256 = '', [string]$Python = '', [switch]$Fresh)
    $ErrorActionPreference = 'Stop'
    $root = $PSScriptRoot
    $log = Join-Path $root 'build\flash.log'
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    $logFile = [IO.File]::Open($log, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $logWriter = [IO.StreamWriter]::new($logFile, [Text.UTF8Encoding]::new($true))
    $logWriter.AutoFlush = $true

    function Log([string]$Message) {
        $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message
        $logWriter.WriteLine($line)
        Write-Host $line
    }

    $source = $null
    try {
        Log "start: disk=$Disk image=$Image"
        if (-not (Test-FlashAdministrator)) {
            Log 'STOP: run from elevated PowerShell or accept UAC in flash-deepos.cmd'
            return 2
        }

        if (-not $Python) {
            $bundled = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
            if (Test-Path -LiteralPath $bundled -PathType Leaf) { $Python = $bundled }
            else { $Python = (Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }
        }
        if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python interpreter not found: $Python" }
        $Python = (Resolve-Path -LiteralPath $Python).ProviderPath
        Log "python=$Python"

        $release = Join-Path $root 'docs\RELEASE.md'
        if (Test-Path -LiteralPath $release -PathType Leaf) {
            if (-not $Sha256) {
                $entry = Select-String -LiteralPath $release -Pattern 'image sha256: `([0-9a-f]{64})`' | Select-Object -First 1
                if ($entry) { $Sha256 = $entry.Matches[0].Groups[1].Value }
            }
            if (-not $Image) {
                $entry = Select-String -LiteralPath $release -Pattern '^\| image \| \d+ \| [0-9a-f]{64} \| `([^`]+)` \|' | Select-Object -First 1
                if ($entry) { $Image = $entry.Matches[0].Groups[1].Value }
            }
        }
        if (-not $Image) { $Image = 'build/deepos-r36s-v20.img' }
        if ($Sha256 -notmatch '^[0-9a-f]{64}$') { throw 'A valid expected SHA-256 is required' }

        if ($env:DEEPOS_CHUNK_KIB -and $env:DEEPOS_CHUNK_KIB -notin @('128', '256', '512', '1024')) {
            throw 'DEEPOS_CHUNK_KIB must be 128, 256, 512 or 1024'
        }
        if ($env:DEEPOS_THROTTLE_MS) {
            $delay = 0.0
            if (-not [double]::TryParse($env:DEEPOS_THROTTLE_MS, [Globalization.NumberStyles]::Float,
                    [Globalization.CultureInfo]::InvariantCulture, [ref]$delay) -or
                [double]::IsInfinity($delay) -or [double]::IsNaN($delay) -or $delay -lt 0) {
                throw 'DEEPOS_THROTTLE_MS must be a finite, nonnegative number'
            }
        }

        $target = Get-FlashDisk $Disk
        $Disk = $target.Number
        Log "target: disk=$Disk $($target.FriendlyName) size=$($target.Size) bus=$($target.BusType) style=$($target.PartitionStyle)"
        if (-not [IO.Path]::IsPathRooted($Image)) { $Image = Join-Path $root $Image }
        if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) { throw "Image file not found: $Image" }
        $Image = (Resolve-Path -LiteralPath $Image).ProviderPath
        # Block other processes from writing or replacing the verified source during the flash.
        $source = [IO.File]::Open($Image, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        if ($source.Length -lt (67 * 512) -or $source.Length % 512) { throw "Invalid image size: $($source.Length)" }
        if ($source.Length -gt $target.Size) { throw "Disk is smaller than the image ($($source.Length) bytes)" }
        Log "checking SHA-256 of $($source.Length) bytes before clearing disk"
        $actual = (Get-FileHash -InputStream $source -Algorithm SHA256 -ErrorAction Stop).Hash
        if ($actual -ne $Sha256) { throw "Image SHA-256 mismatch: expected=$Sha256 actual=$actual" }
        Log "source verified: sha256=$actual"

        $current = Get-FlashDisk $Disk
        if ($current.Path -ne $target.Path -or $current.UniqueId -ne $target.UniqueId -or
            $current.SerialNumber -ne $target.SerialNumber) { throw 'Disk identity changed before clearing' }
        if ($current.NumberOfPartitions -ne 0) {
            Log 'clearing partition table'
            Clear-Disk -InputObject $current -RemoveData -RemoveOEM -Confirm:$false -ErrorAction Stop
            Log 'Clear-Disk: OK'
        } else {
            Log 'Windows reports no partitions to remove'
        }

        # Wait for the storage stack to drop the old volume objects before opening the raw disk.
        for ($attempt = 0; $attempt -lt 10; $attempt++) {
            Update-HostStorageCache -ErrorAction Stop
            $ready = Get-FlashDisk $Disk
            if ($ready.Path -ne $target.Path -or $ready.SerialNumber -ne $target.SerialNumber) {
                throw 'Disk identity changed after clearing'
            }
            if ($ready.PartitionStyle -in @('RAW', 'MBR', 'GPT') -and $ready.NumberOfPartitions -eq 0) { break }
            Start-Sleep -Seconds 1
        }
        if ($ready.PartitionStyle -notin @('RAW', 'MBR', 'GPT') -or $ready.NumberOfPartitions -ne 0) {
            throw "Old partition layout remains visible: $($ready.PartitionStyle), $($ready.NumberOfPartitions) partitions"
        }
        Log "ready: style=$($ready.PartitionStyle) partitions=0"

        $flashArgs = @('-u', (Join-Path $root 'tools\dpflash.py'), '--image', $Image,
                       '--target', "\\.\PhysicalDrive$Disk", '--expect-sha256', $Sha256,
                       '--disk-path', $ready.Path, '--disk-size', ([string]$ready.Size),
                       '--verify')
        if (-not $Fresh) { $flashArgs += '--resume' }
        if ($ready.SerialNumber) { $flashArgs += @('--disk-serial', $ready.SerialNumber.Trim()) }
        Log 'writing image'
        try {
            # PowerShell 5.1 wraps redirected native stderr in ErrorRecord objects.
            # Keep streaming those lines and preserve the native exit status.
            $ErrorActionPreference = 'Continue'
            & $Python @flashArgs 2>&1 | ForEach-Object { Log "  $_" }
            $code = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = 'Stop'
        }
        Log "dpflash exit=$code"
        if ($code -ne 0) { return $code }
        Log 'DONE: image written and verified'
        return 0
    } catch {
        Log "STOP: $($_.Exception.Message)"
        return 1
    } finally {
        if ($null -ne $source) { $source.Dispose() }
        $logWriter.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    exit (Invoke-DeepOSFlash @PSBoundParameters)
}
