# Runs pre-commit on all files, auto-staging any formatter changes (e.g. Black),
# then re-running once so the final result is a clean pass.
#
# Usage:
#   pwsh -File scripts/precommit_all.ps1

$ErrorActionPreference = "Stop"

function Get-GitStatusPorcelain {
    try {
        return (git status --porcelain)
    } catch {
        return $null
    }
}

$before = Get-GitStatusPorcelain

Write-Host "Running: pre-commit run --all-files" -ForegroundColor Cyan
pre-commit run --all-files
$exitCode = $LASTEXITCODE

$after = Get-GitStatusPorcelain

if ($exitCode -ne 0 -and $after -ne $before) {
    Write-Host "Hooks modified files (formatters). Staging tracked changes and re-running..." -ForegroundColor Yellow
    git add -u

    pre-commit run --all-files
    $exitCode = $LASTEXITCODE
}

exit $exitCode
