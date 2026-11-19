param([string]$Python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source)
$ErrorActionPreference = 'Stop'
$interpreter = $Python
$repo = Split-Path $PSScriptRoot
$tmp = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
try {
    New-Item -ItemType Directory $tmp, (Join-Path $tmp 'tools') | Out-Null
    Copy-Item (Join-Path $repo 'flash-deepos.ps1') $tmp
    . (Join-Path $tmp 'flash-deepos.ps1')
    $image = Join-Path $tmp 'verified card.img'
    [IO.File]::WriteAllBytes($image, [byte[]]::new(34816))
    $sha = (Get-FileHash -LiteralPath $image).Hash
    $packed = $image + '.gz'
    & $interpreter -c 'import gzip, pathlib, sys; pathlib.Path(sys.argv[2]).write_bytes(gzip.compress(pathlib.Path(sys.argv[1]).read_bytes()))' $image $packed
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the compressed image fixture' }
    $log = Join-Path $tmp 'build\flash.log'
    $env:DEEPOS_TEST_FLASH_MARKER = Join-Path $tmp 'python-called'
    @"
import gzip
import hashlib
import os
import pathlib
import sys
import time

if "--inspect-image" in sys.argv:
    image = pathlib.Path(sys.argv[sys.argv.index("--image") + 1])
    data = gzip.decompress(image.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    if digest != sys.argv[sys.argv.index("--expect-sha256") + 1].lower():
        sys.exit(1)
    print(len(data), digest)
    sys.exit(0)
assert "--verify" in sys.argv and "--expand" not in sys.argv
assert "--resume" not in sys.argv and r"\\.\PhysicalDrive2" in sys.argv
pathlib.Path(os.environ["DEEPOS_TEST_FLASH_MARKER"]).write_text("started")
print("streamed progress", flush=True)
for attempt in range(100):
    if "streamed progress" in pathlib.Path(r"$log").read_text(encoding="utf-8-sig"):
        break
    time.sleep(.02)
else:
    sys.exit(92)
print("simulated failure", file=sys.stderr, flush=True)
sys.exit(23)
"@ | Set-Content -Encoding ASCII (Join-Path $tmp 'tools\dpflash.py')

    function Test-FlashAdministrator { return $true }
    function Get-Disk {
        [CmdletBinding()]
        param()
        $p = [pscustomobject]@{
            Number = 2; Path = '\\?\device1'; UniqueId = 'id1'; SerialNumber = 'serial1'
            FriendlyName = 'Generic STORAGE DEVICE'; Size = 53745811456; BusType = 'USB'
            IsBoot = $false; IsSystem = $false; IsReadOnly = $false; IsOffline = $false
            PartitionStyle = 'GPT'; NumberOfPartitions = 4; LogicalSectorSize = 512
        }
        if ($script:clears -and $script:case -ne 'old-layout') {
            $p.PartitionStyle = if ($script:case -eq 'empty-gpt') { 'GPT' } else { 'MBR' }
            $p.NumberOfPartitions = 0
        }
        if ($script:case -eq 'already-empty') { $p.NumberOfPartitions = 0 }
        if ($script:case -eq 'small') { $p.Size = 512 }
        if ($script:case -eq 'new-card') { $p.Size = 31104958464 }
        if ($script:case -eq 'sector') { $p.LogicalSectorSize = 4096 }
        if ($script:case -eq 'system') { $p.IsSystem = $true }
        $p
        if ($script:case -eq 'ambiguous') { $p }
    }
    function Clear-Disk {
        [CmdletBinding(SupportsShouldProcess)]
        param($InputObject, [switch]$RemoveData, [switch]$RemoveOEM)
        $script:clears++
        try {
            $writer = [IO.File]::Open($runImage, [IO.FileMode]::Open, [IO.FileAccess]::Write)
            $writer.Dispose()
            $script:sourceUnlocked = $true
        } catch [IO.IOException] {}
        if ($script:case -eq 'clear-error') { throw 'mock clear error' }
    }
    function Update-HostStorageCache { [CmdletBinding()] param() }
    function Start-Sleep { param([int]$Seconds) }

    foreach ($script:case in 'sha', 'small', 'sector', 'system', 'ambiguous', 'clear-error', 'old-layout', 'python-error', 'empty-gpt', 'already-empty', 'new-card', 'gzip', 'gzip-bad-sha') {
        $script:clears = 0
        $script:sourceUnlocked = $false
        Remove-Item -LiteralPath $env:DEEPOS_TEST_FLASH_MARKER -ErrorAction SilentlyContinue
        $expectedSha = $sha
        if ($script:case -in @('sha', 'gzip-bad-sha')) { $expectedSha = '0' * 64 }
        $runImage = if ($script:case -in @('gzip', 'gzip-bad-sha')) { $packed } else { $image }
        $code = Invoke-DeepOSFlash -Image $runImage -Sha256 $expectedSha -Python $interpreter -Fresh
        $wrote = Test-Path -LiteralPath $env:DEEPOS_TEST_FLASH_MARKER
        if ($script:case -in @('clear-error', 'old-layout', 'python-error', 'empty-gpt', 'new-card', 'gzip')) { $expectedClears = 1 }
        else { $expectedClears = 0 }
        if ($script:clears -ne $expectedClears) { throw "Wrong number of clear calls for $($script:case)" }
        if ($script:sourceUnlocked) { throw 'Source allowed writes after verification' }
        if ($script:case -in @('python-error', 'empty-gpt', 'already-empty', 'new-card', 'gzip')) {
            if ($code -ne 23 -or -not $wrote) { throw "Expected child error 23, got $code" }
            $lines = Get-Content -LiteralPath $log
            if (($lines -match 'simulated failure').Count -ne 1 -or ($lines -match 'DONE').Count) {
                throw 'Unexpected failure log'
            }
        } elseif ($code -ne 1 -or $wrote) { throw "Expected guarded failure for $($script:case), got $code" }
    }

    $launch = (Get-Content (Join-Path $repo 'flash-deepos.cmd') | Where-Object { $_ -like 'powershell *' })
    $payload = [regex]::Match($launch, '-Command "(.*)"$').Groups[1].Value
    $mock = @"
function Start-Process {
    param(`$FilePath, `$Verb, [switch]`$Wait, [switch]`$PassThru, [string[]]`$ArgumentList)
    `$expected = [char]34 + 'C:\test path\flash-deepos.ps1' + [char]34
    if (-not (`$Wait -and `$PassThru) -or `$ArgumentList[-1] -ne `$expected) { throw 'Invalid launcher arguments' }
    [pscustomobject]@{ ExitCode = 23 }
}
`$env:DEEPOS_FLASH_SCRIPT = 'C:\test path\flash-deepos.ps1'
"@
    $encoding = [Text.Encoding]::Unicode
    $encoded = [Convert]::ToBase64String($encoding.GetBytes($mock + "`n" + $payload))
    & powershell.exe -NoProfile -EncodedCommand $encoded
    if ($LASTEXITCODE -ne 23) { throw "Elevated launcher lost the child exit code: $LASTEXITCODE" }
    Write-Host 'PASS Windows flash wrapper guards, streamed logs and child error propagation'
} finally {
    Remove-Item Env:DEEPOS_TEST_FLASH_MARKER -ErrorAction SilentlyContinue
    $allowed = [IO.Path]::GetTempPath()
    if ($tmp.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $tmp -Recurse -Force
    }
}
