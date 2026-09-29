param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$prefix = $root + [IO.Path]::DirectorySeparatorChar
$plan = Get-Content -LiteralPath (Join-Path $root 'config/layout_migration_20260929.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$auditDir = Join-Path $root 'local/migration_20260929'
$manifestPath = Join-Path $auditDir 'manifest.json'

function Safe-Path([string]$relative) {
    $full = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Outside workspace: $relative" }
    return $full
}
function New-Relative([string]$relative) {
    foreach ($move in ($plan.moves | Sort-Object { $_.from.Length } -Descending)) {
        if ($relative -eq $move.from) { return $move.to }
        if ($relative.StartsWith($move.from + '/', [StringComparison]::OrdinalIgnoreCase)) {
            return $move.to + $relative.Substring($move.from.Length)
        }
    }
    return $relative
}
function Walk-Local([string]$directory) {
    foreach ($item in (Get-ChildItem -LiteralPath $directory -Force)) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item }
        elseif ($item.PSIsContainer) { Walk-Local $item.FullName }
        else { $item }
    }
}

# Inventory each affected top-level tree once; never traverse junction targets.
$tops = @($plan.moves | ForEach-Object { ($_.from -split '/')[0] } | Sort-Object -Unique)
$rows = [Collections.Generic.List[object]]::new()
$destinations = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($top in $tops) {
    $source = Safe-Path $top
    if (-not (Test-Path -LiteralPath $source)) { throw "Missing migration source: $source" }
    $item = Get-Item -LiteralPath $source -Force
    $items = if ($item.PSIsContainer) { @(Walk-Local $source) } else { @($item) }
    foreach ($file in $items) {
        $old = $file.FullName.Substring($prefix.Length).Replace('\','/')
        $new = New-Relative $old
        $target = Safe-Path $new
        if (-not $destinations.Add($new)) { throw "Destination collision: $new" }
        if (Test-Path -LiteralPath $target) { throw "Destination already exists: $new" }
        $link = [bool]($file.Attributes -band [IO.FileAttributes]::ReparsePoint)
        $rows.Add(@{from=$old; to=$new; bytes=($(if ($link) {0} else {$file.Length})); link=$link; target=($(if($link){$file.Target}else{$null}))})
    }
}
Write-Output "Validated $($rows.Count) affected files/links; no destination collisions."
if (-not $Apply) { exit 0 }
if (Test-Path -LiteralPath $manifestPath) { throw 'Migration manifest already exists; inspect before resuming.' }
New-Item -ItemType Directory -Path $auditDir -Force | Out-Null
$i = 0
foreach ($row in $rows) {
    if (-not $row.link) { $row.sha256 = (Get-FileHash -LiteralPath (Safe-Path $row.from) -Algorithm SHA256).Hash.ToLowerInvariant() }
    $i++
    if ($i % 5000 -eq 0) { Write-Output "Fingerprinted $i / $($rows.Count)" }
}
@{status='planned'; baseline_commit=$plan.baseline_commit; files=$rows} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8

function Move-Tree([string]$source, [string]$target) {
    if (-not $source.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe move path' }
    $item = Get-Item -LiteralPath $source -Force
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Move-Item -LiteralPath $source -Destination $target
    } elseif ($item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        foreach ($child in (Get-ChildItem -LiteralPath $source -Force)) { Move-Tree $child.FullName (Join-Path $target $child.Name) }
        # Only an empty directory can be removed here; no recursive deletion.
        Remove-Item -LiteralPath $source
    } else { throw "Refuse overwrite: $target" }
}
foreach ($move in $plan.moves) {
    $source = Safe-Path $move.from
    if (Test-Path -LiteralPath $source) {
        Move-Tree $source (Safe-Path $move.to)
        Write-Output "Moved $($move.from) -> $($move.to)"
    }
}
$i = 0
foreach ($row in $rows) {
    $target = Safe-Path $row.to
    if ($row.link) {
        $item = Get-Item -LiteralPath $target -Force
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or ($item.Target -join '|') -ne ($row.target -join '|')) { throw "Changed link: $target" }
    } elseif ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256) { throw "Hash mismatch: $target" }
    $i++
    if ($i % 5000 -eq 0) { Write-Output "Verified $i / $($rows.Count)" }
}
@{status='verified_before_reference_updates'; baseline_commit=$plan.baseline_commit; files=$rows} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$summary = @{date=$plan.date; baseline_commit=$plan.baseline_commit; files_and_links=$rows.Count; bytes=($rows|Measure-Object bytes -Sum).Sum; all_moved_hashes_verified=$true; junction_targets_untouched=$true; moves=$plan.moves; full_manifest='local/migration_20260929/manifest.json'}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'docs/repository/migration_summary_20260929.json') -Encoding utf8
Write-Output 'All moves and content hashes verified. No source data deleted.'
