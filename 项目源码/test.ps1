param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location -LiteralPath $PackageRoot
try {
    & $Python -m unittest tests.test_single_file_cycle_workbench tests.test_three_year_audit -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed." }
    & $Python tools/anhui_web/verify_single_file_v12.py prebuild
    if ($LASTEXITCODE -ne 0) { throw "v12 prebuild verification failed." }
    & $Python tools/anhui_web/verify_single_file_v12.py postbuild
    if ($LASTEXITCODE -ne 0) { throw "v12 postbuild verification failed." }
    & node --test tests/test_wanyu_core.cjs
    if ($LASTEXITCODE -ne 0) { throw "Node core tests failed." }
}
finally {
    Pop-Location
}
