param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path,
    [string]$PackageName = "皖域择岗交接包_v17.6.4_20260904_换设备"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$handoffRoot = Join-Path $desktop $PackageName
$zipPath = "$handoffRoot.zip"
$originalArchive = "E:\zcode\皖域择岗交接包_20260904_v17.6.4.tar.gz"

if (Test-Path -LiteralPath $handoffRoot) { throw "目标文件夹已存在，不覆盖：$handoffRoot" }
if (Test-Path -LiteralPath $zipPath) { throw "目标压缩包已存在，不覆盖：$zipPath" }
if (-not (Test-Path -LiteralPath $originalArchive -PathType Leaf)) { throw "找不到原始交接包：$originalArchive" }

New-Item -ItemType Directory -Path $handoffRoot -Force | Out-Null

function Get-ExcludedDirectories {
    param([string]$Root)
    $excluded = New-Object System.Collections.Generic.List[string]
    foreach ($name in @("node_modules", "__pycache__", ".pytest_cache")) {
        Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq $name } |
            ForEach-Object { [void]$excluded.Add($_.FullName) }
    }
    [void]$excluded.Add((Join-Path $Root "deliverables\maintainable"))
    return $excluded.ToArray()
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludedDirectories = @()
    )
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $args = @($Source, $Destination, "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    if ($ExcludedDirectories.Count -gt 0) {
        $args += "/XD"
        $args += $ExcludedDirectories
    }
    $args += "/XF"
    $args += @("*.pyc", "Thumbs.db", ".DS_Store", "_dl_continue.py", "_register_continue.py", "_inventory_continue_round3.py", "downloaded_*.jsonl")
    & robocopy @args | Out-Host
    if ($LASTEXITCODE -gt 7) { throw "复制失败：$Source -> $Destination，robocopy=$LASTEXITCODE" }
}

$projectDestination = Join-Path $handoffRoot "项目源码"
$excludedDirectories = Get-ExcludedDirectories -Root $projectRoot
Copy-Tree -Source $projectRoot -Destination $projectDestination -ExcludedDirectories $excludedDirectories

$fullSite = Join-Path (Split-Path -Parent $projectRoot) "site"
$liteSite = Join-Path (Split-Path -Parent (Split-Path -Parent $projectRoot)) "wan-lite\site"
Copy-Tree -Source $fullSite -Destination (Join-Path $handoffRoot "网站")
Copy-Tree -Source $liteSite -Destination (Join-Path $handoffRoot "网站-lite")

Copy-Item -LiteralPath $originalArchive -Destination (Join-Path $handoffRoot "原始交接包\皖域择岗交接包_20260904_v17.6.4.tar.gz") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "HANDOFF_换设备_v17.6.4.md") -Destination (Join-Path $handoffRoot "README_先看这里.md") -Force

$componentLines = New-Object System.Collections.Generic.List[string]
[void]$componentLines.Add("皖域择岗交接包 v17.6.4 · 2026-09-04")
[void]$componentLines.Add("桌面目录：$handoffRoot")
[void]$componentLines.Add("主入口：网站\index.html")
[void]$componentLines.Add("")
foreach ($component in @("项目源码", "网站", "网站-lite", "原始交接包")) {
    $componentPath = Join-Path $handoffRoot $component
    $measure = Get-ChildItem -LiteralPath $componentPath -Recurse -File -Force | Measure-Object -Property Length -Sum
    $bytes = if ($measure.Sum) { [int64]$measure.Sum } else { 0 }
    $count = if ($measure.Count) { [int]$measure.Count } else { 0 }
    [void]$componentLines.Add(("{0}: {1} files / {2:N0} bytes" -f $component, $count, $bytes))
}
[void]$componentLines.Add("")
[void]$componentLines.Add("排除：node_modules、__pycache__、.pytest_cache、*.pyc 及已知临时下载脚本/日志。")
[void]$componentLines.Add("正式数据基线未因 supplement 台账追加；证据台账位于项目源码\source_data\supplement_20260904\integrity_audit.json。")
$componentLines | Set-Content -LiteralPath (Join-Path $handoffRoot "交接包清单.txt") -Encoding UTF8

Compress-Archive -LiteralPath $handoffRoot -DestinationPath $zipPath -CompressionLevel Optimal
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
$zipInfo = Get-Item -LiteralPath $zipPath

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entryNames = @($archive.Entries | ForEach-Object { $_.FullName })
} finally {
    $archive.Dispose()
}
$required = @(
    "$PackageName/网站/index.html",
    "$PackageName/网站/data/site-manifest.json",
    "$PackageName/网站/data/audit/supplement-20260904.json",
    "$PackageName/项目源码/source_data/supplement_20260904/integrity_audit.json",
    "$PackageName/项目源码/HANDOFF_换设备_v17.6.4.md",
    "$PackageName/原始交接包/皖域择岗交接包_20260904_v17.6.4.tar.gz"
)
$missing = @($required | Where-Object { $entryNames -notcontains $_ })
if ($missing.Count -gt 0) { throw "压缩包缺少必需条目：$($missing -join ', ')" }

$sidecar = "$zipPath.sha256.txt"
@(
    "SHA256  $zipHash",
    "BYTES   $($zipInfo.Length)",
    "ENTRIES $($entryNames.Count)",
    "FILE    $zipPath"
) | Set-Content -LiteralPath $sidecar -Encoding ASCII

Write-Output (ConvertTo-Json ([ordered]@{
    folder = $handoffRoot
    zip = $zipPath
    zip_sha256 = $zipHash
    zip_bytes = $zipInfo.Length
    zip_entries = $entryNames.Count
    sidecar = $sidecar
    required_entries = $required.Count
    missing_entries = $missing.Count
}) -Compress)
