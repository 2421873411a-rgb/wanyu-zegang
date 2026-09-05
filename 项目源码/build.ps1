param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location -LiteralPath $PackageRoot
try {
    & $Python -m pip install -r .\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }

    & $Python .\tools\anhui_web\audit_three_years.py `
        --root $PackageRoot `
        --output-json (Join-Path $PackageRoot "tools\anhui_web\data\three_year_audit.json") `
        --report (Join-Path $PackageRoot "docs\三年数据真实性与完整性审计_v12.md")
    if ($LASTEXITCODE -ne 0) { throw "Three-year data audit failed." }

    foreach ($Cycle in @("2026", "2025", "2024")) {
        & $Python .\tools\anhui_web\build_score_lists.py --cycle $Cycle
        if ($LASTEXITCODE -ne 0) { throw "Score list build failed for cycle $Cycle." }
    }

    & $Python .\tools\anhui_web\build_pages.py `
        --output-dir ".\deliverables"
    if ($LASTEXITCODE -ne 0) { throw "HTML build failed." }

    Write-Host "Built one offline single-file workbench containing 2024/2025/2026."
}
finally {
    Pop-Location
}
