$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bundle = Join-Path $root 'research_materials'
$snapshot = Join-Path $bundle '90_material_snapshot'
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$extensions = @('.md', '.pdf', '.tex', '.bib', '.py', '.java', '.json', '.csv', '.png', '.svg', '.yaml', '.yml', '.ps1')
$trees = @('articles', 'calculation and paper', 'simulation/docs', 'simulation/scripts', 'docs', 'analysis/background_field_reference_20260927', 'analysis/source_scale_groundwork_20260925')
$files = foreach ($tree in $trees) {
    Get-ChildItem -LiteralPath (Join-Path $root $tree) -File -Recurse | Where-Object {
        $_.Extension -in $extensions -and $_.FullName -notmatch '[\\/](build|__pycache__|\.pytest_cache|docx_analysis)[\\/]'
    }
}
$files += Get-ChildItem -LiteralPath (Join-Path $root 'results') -File -Recurse -Filter '*.md'
$extra = @('PROJECT_STATE.md', 'information.md', 'scripts/background_field_reference_20260927.py', 'tests/test_background_field_reference_20260927.py', 'scripts/source_scale_groundwork_20260925.py')
$files += $extra | ForEach-Object { Get-Item -LiteralPath (Join-Path $root $_) }
$manifest = foreach ($file in ($files | Sort-Object FullName -Unique)) {
    if ($file.Length -gt 30MB) { throw "Unexpected large material: $($file.FullName)" }
    $relative = $file.FullName.Substring($root.Length + 1)
    $target = Join-Path $snapshot $relative
    New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) {
            throw "Existing snapshot differs; not overwriting: $target"
        }
    } else { Copy-Item -LiteralPath $file.FullName -Destination $target }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw "Copy mismatch: $relative" }
    [pscustomobject]@{source=$file.FullName; copy=$target; bytes=$file.Length; sha256=$hash}
}
$manifest | Export-Csv -LiteralPath (Join-Path $bundle 'material_manifest.csv') -NoTypeInformation -Encoding utf8
$modelManifest = Get-ChildItem -LiteralPath (Join-Path $root 'simulation/models') -File -Filter '*.mph' | ForEach-Object {
    [pscustomobject]@{path=$_.FullName; bytes=$_.Length; modified=$_.LastWriteTime.ToString('s'); handling='original retained; indexed, not copied'}
}
$modelManifest | Export-Csv -LiteralPath (Join-Path $bundle 'existing_comsol_model_index.csv') -NoTypeInformation -Encoding utf8
[pscustomobject]@{copied_files=$manifest.Count; copied_MB=[math]::Round(($manifest | Measure-Object bytes -Sum).Sum/1MB,2); indexed_mph=$modelManifest.Count; ppt_touched=$false} | ConvertTo-Json
