<#
.SYNOPSIS
    Блокирует попадание чувствительных данных в репозиторий DEEPoS.

.DESCRIPTION
    Сканирует текстовые файлы рабочего дерева (или только staged-изменения)
    и падает с exit 1, если находит локальные IP, токены, ключи, серийники,
    почтовые адреса и пути к домашним каталогам.

.PARAMETER Staged
    Проверять только то, что уже добавлено в индекс (режим pre-commit).

.PARAMETER Quiet
    Печатать только проблемы, без итоговой сводки.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\check-secrets.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\check-secrets.ps1 -Staged
#>
[CmdletBinding()]
param(
    [switch]$Staged,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    # --- какой набор файлов проверяем -------------------------------------
    if ($Staged) {
        $files = git diff --cached --name-only --diff-filter=ACMR 2>$null
    }
    else {
        $files = git ls-files 2>$null
    }

    $allowedExt = @('.md', '.txt', '.html', '.htm', '.cjs', '.js', '.mjs', '.ts', '.py',
        '.ps1', '.sh', '.toml', '.cfg', '.conf', '.yml', '.yaml', '.json', '.dts',
        '.dtsi', '.config', '.gitignore', '.gitattributes', '.service', '.path',
        '.timer', '.ini', '.env.example')

    $files = $files | Where-Object {
        $f = $_
        $f -and -not ($f -match '(^|/)(node_modules|\.git)/') -and $f -ne 'tools/check-secrets.ps1' -and
        -not ($f -match '^tests/golden/') -and -not ($f -match '^docs/RELEASE\.md$') -and
    -not ($f -match '^tests/') -and -not ($f -match '^board/r36s-v20/') -and
        ($allowedExt -contains [System.IO.Path]::GetExtension($f))
    }

    # --- правила ----------------------------------------------------------
    # каждый элемент: имя, regex, серьёзность (ERROR/WARN), подсказка
    $rules = @(
        @{ Name = 'device-ip-169254';  Sev = 'ERROR'; Rx = '169\.254\.\d{1,3}\.\d{1,3}';            Hint = 'IP-адрес конкретной консоли → <console-ip>' }
        @{ Name = 'device-ip-192168';  Sev = 'ERROR'; Rx = '192\.168\.(?!137\.0/24)\d{1,3}\.\d{1,3}'; Hint = 'IP-адрес конкретного устройства → <console-ip> / <pc-ip>' }
        @{ Name = 'host-key';          Sev = 'ERROR'; Rx = 'SHA256:[A-Za-z0-9+/]{40,}';              Hint = 'SSH host-key/pinning → <host-key>' }
        @{ Name = 'private-key';       Sev = 'ERROR'; Rx = '-----BEGIN [A-Z ]*PRIVATE KEY-----';     Hint = 'приватный ключ нельзя коммитить' }
        @{ Name = 'hex-token-32';      Sev = 'ERROR'; Rx = '\b[0-9a-f]{32}\b';                       Hint = 'похоже на токен/секрет 32 hex → <token>' }
        @{ Name = 'hex-token-64';      Sev = 'ERROR'; Rx = '\b[0-9a-f]{64}\b';                       Hint = 'похоже на секрет/хэш-ключ 64 hex' }
        @{ Name = 'usb-serial';        Sev = 'ERROR'; Rx = 'VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}\\[0-9A-Z]{12,}'; Hint = 'серийник USB-устройства → VID/PID без серийника' }
        @{ Name = 'mac-address';       Sev = 'ERROR'; Rx = '\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'; Hint = 'MAC-адрес → <mac>' }
        @{ Name = 'windows-user-path'; Sev = 'ERROR'; Rx = 'C:\\Users\\(?!<)[^\\\s]+';              Hint = 'локальный путь с именем пользователя → ~ или <repo>' }
        @{ Name = 'corporate-email';   Sev = 'ERROR'; Rx = '[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|archr\.local|deepos\.local|r36s\.local)[A-Za-z0-9.-]+\.[A-Za-z]{2,}'; Hint = 'личная/корпоративная почта → убрать' }
        @{ Name = 'panel-token-word';  Sev = 'ERROR'; Rx = '(?i)(token|secret|passwd|password)\s*[:=]\s*["'']?[A-Za-z0-9_\-]{8,}'; Hint = 'секрет в присваивании → плейсхолдер' }
        @{ Name = 'default-password';  Sev = 'WARN';  Rx = '(?i)пароль[^.\n]{0,40}\barchr\b';        Hint = 'дефолтный пароль Arch-R — публично известен, но лучше сослаться на документацию' }
    )

    $problems = New-Object System.Collections.Generic.List[object]

    foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath $file)) { continue }
        $lineNo = 0
        foreach ($line in [System.IO.File]::ReadLines((Resolve-Path -LiteralPath $file))) {
            $lineNo++
            if ($line.Length -gt 4000) { continue }   # битые/минифицированные строки не разбираем
            foreach ($rule in $rules) {
                # Published build hashes are not secrets: skip hex rules on
                # lines that name them explicitly (sha256 / sha-256 / md5).
                if ($rule.Name -like 'hex-token-*' -and $line -match '(?i)sha-?256|\bmd5\b') {
                    continue
                }
                if ($line -match $rule.Rx) {
                    $problems.Add([pscustomobject]@{
                            File = $file; Line = $lineNo; Rule = $rule.Name
                            Sev  = $rule.Sev; Hint = $rule.Hint; Text = $line.Trim()
                        })
                }
            }
        }
    }

    # --- вывод ------------------------------------------------------------
    $errors = @($problems | Where-Object Sev -eq 'ERROR')
    $warns = @($problems | Where-Object Sev -eq 'WARN')

    foreach ($p in $problems) {
        $short = if ($p.Text.Length -gt 120) { $p.Text.Substring(0, 120) + '…' } else { $p.Text }
        Write-Host ("[{0}] {1}:{2}  ({3})" -f $p.Sev, $p.File, $p.Line, $p.Rule) -ForegroundColor $(if ($p.Sev -eq 'ERROR') { 'Red' } else { 'Yellow' })
        Write-Host ("        {0}" -f $short) -ForegroundColor DarkGray
        Write-Host ("        → {0}" -f $p.Hint) -ForegroundColor DarkGray
    }

    if (-not $Quiet) {
        Write-Host ''
        Write-Host ("проверено файлов: {0} · ошибок: {1} · предупреждений: {2}" -f $files.Count, $errors.Count, $warns.Count)
    }

    if ($errors.Count -gt 0) {
        Write-Host ''
        Write-Host 'КОММИТ ЗАБЛОКИРОВАН: уберите чувствительные данные (см. AGENTS.md §4).' -ForegroundColor Red
        exit 1
    }
    exit 0
}
finally {
    Pop-Location
}
