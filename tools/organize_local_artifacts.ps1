param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$prefix = $root + [IO.Path]::DirectorySeparatorChar
$manifest = Join-Path $root 'docs/repository/local_moves_20260928.json'

function In-Workspace([string]$relative) {
    $full = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace: $relative"
    }
    return $full
}

$moves = [Collections.Generic.List[object]]::new()
Get-ChildItem -LiteralPath $root -File | Where-Object {
    $_.Name -like '26.8.12*.pptx*'
} | ForEach-Object {
    $moves.Add(@{from=$_.Name; to=('output/presentations/20260812/' + $_.Name)})
}
Get-ChildItem -LiteralPath $root -Directory | Where-Object {
    $_.Name -like '26.8.12*'
} | ForEach-Object {
    $moves.Add(@{from=$_.Name; to=('output/presentations/20260812/rendered/' + $_.Name)})
}
Get-ChildItem -LiteralPath $root -File -Filter 'VD230*.pdf' | ForEach-Object {
    $moves.Add(@{from=$_.Name; to=('docs/equipment/' + $_.Name)})
}
Get-ChildItem -LiteralPath $root -Directory -Filter 'analysis_package_*' | ForEach-Object {
    $moves.Add(@{from=$_.Name; to=('local_archive/legacy_packages/' + $_.Name)})
}
foreach ($name in @('analysis_package_stderr.log', 'analysis_package_stdout.log')) {
    if (Test-Path -LiteralPath (Join-Path $root $name)) {
        $moves.Add(@{from=$name; to=('logs/legacy_packages/' + $name)})
    }
}
if (Test-Path -LiteralPath (Join-Path $root '$build')) {
    $moves.Add(@{from='$build'; to='local_archive/scratch_build'})
}

# Validate all source/destination paths and fingerprint before any move.
$files = [Collections.Generic.List[object]]::new()
foreach ($move in $moves) {
    $source = In-Workspace $move.from
    $target = In-Workspace $move.to
    if (Test-Path -LiteralPath $target) { throw "Destination exists: $target" }
    $item = Get-Item -LiteralPath $source -Force
    $children = if ($item.PSIsContainer) {
        @(Get-ChildItem -LiteralPath $source -File -Recurse -Force)
    } else { @($item) }
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refuse reparse point: $source"
    }
    foreach ($file in $children) {
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refuse reparse point: $($file.FullName)"
        }
        $suffix = if ($item.PSIsContainer) { $file.FullName.Substring($source.Length + 1) } else { '' }
        $destFile = if ($suffix) { Join-Path $target $suffix } else { $target }
        $files.Add(@{
            from=$file.FullName.Substring($prefix.Length).Replace('\','/')
            to=$destFile.Substring($prefix.Length).Replace('\','/')
            bytes=$file.Length
            sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        })
    }
}
if (-not $Apply) {
    $moves | ConvertTo-Json -Depth 4
    Write-Output "Dry run: $($files.Count) files. Use -Apply to move without overwriting."
    exit 0
}
if (Test-Path -LiteralPath $manifest) { throw 'Existing move manifest; refusing to overwrite.' }
New-Item -ItemType Directory -Path (Split-Path -Parent $manifest) -Force | Out-Null
@{date='2026-09-28'; status='planned'; moves=$moves; files=$files} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifest -Encoding utf8
foreach ($move in $moves) {
    $source = In-Workspace $move.from
    $target = In-Workspace $move.to
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Move-Item -LiteralPath $source -Destination $target
}
foreach ($file in $files) {
    $hash = (Get-FileHash -LiteralPath (In-Workspace $file.to) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $file.sha256) { throw "Verification failed: $($file.to)" }
    if (Test-Path -LiteralPath (In-Workspace $file.from)) { throw "Source still exists: $($file.from)" }
}
@{date='2026-09-28'; status='verified'; moves=$moves; files=$files} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifest -Encoding utf8
Write-Output "Moved and SHA-256 verified $($files.Count) files in $($moves.Count) groups."
