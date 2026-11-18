<#
.SYNOPSIS
    Включает локальные проверки DEEPoS: git-хук против секретов.

.DESCRIPTION
    Устанавливает core.hooksPath=.githooks, проверяет, что хук исполняется,
    и прогоняет сканер по всему дереву.
#>
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    git config core.hooksPath .githooks
    Write-Host 'core.hooksPath = .githooks'

    $hook = Join-Path $repo '.githooks\pre-commit'
    if (Test-Path $hook) {
        # снять CRLF/BOM, если файл случайно отредактировали в Windows
        $bytes = [System.IO.File]::ReadAllBytes($hook)
        if ($bytes.Length -gt 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            [System.IO.File]::WriteAllBytes($hook, $bytes[3..($bytes.Length - 1)])
            Write-Host 'BOM удалён из pre-commit'
        }
        $text = [System.IO.File]::ReadAllText($hook)
        if ($text -match "`r") {
            [System.IO.File]::WriteAllText($hook, ($text -replace "`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
            Write-Host 'CRLF заменён на LF в pre-commit'
        }
    }

    Write-Host ''
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\check-secrets.ps1')
    Write-Host ''
    Write-Host 'Готово: коммит с секретами теперь блокируется.'
}
finally {
    Pop-Location
}