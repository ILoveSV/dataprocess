param([switch]$RemoveRetired)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$prefix = $root.TrimEnd('\') + '\'
$destination = Join-Path $root 'snapshots\thesis_planning_20260926'
$retired = @(
    'docs/PROJECT_CONTEXT_FOR_CONTINUATION.md',
    'docs/PROJECT_HANDOFF_TO_GPT6_20260906.md',
    'docs/RESEARCH_PROGRESS_REVIEW_20260906.md',
    'docs/MENTOR_ALIGNED_ANALYSIS_CONTEXT_20260828.md',
    'docs/论文背景与总体框架_导师讨论稿_20260915.md',
    'docs/毕业论文非实验工作路线图_20260908.md'
)
$preserved = @(
    'PROJECT_STATE.md', 'information.md',
    'docs/导师组会意见与当前任务_20260920.md',
    'docs/RESEARCH_REVIEW_FILE_AUDIT_20260906.md',
    'docs/COMSOL仿真执行计划书_20260908.md',
    'calculation and paper/舰艇电场纯理论计算任务说明_v0.1.md',
    'calculation and paper/biyelunwen/thesis_latex/README.md',
    'calculation and paper/biyelunwen/thesis_latex/chapters/chapter01_introduction.tex',
    'calculation and paper/biyelunwen/thesis_latex/references.tex'
)
function Get-CheckedPath([string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace: $path"
    }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Expected existing file: $path"
    }
    return (Get-Item -LiteralPath $path).FullName
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = Join-Path $destination 'before_update.zip'
$manifestPath = Join-Path $destination 'manifest.json'
if (-not $RemoveRetired) {
    if (Test-Path -LiteralPath $destination) { throw 'Snapshot already exists; refusing overwrite.' }
    $records = foreach ($relative in @($retired) + @($preserved)) {
        $path = Get-CheckedPath $relative
        [pscustomobject]@{
            path = $relative
            action = $(if ($retired -contains $relative) { 'retire_after_verification' } else { 'backup_before_update' })
            bytes = (Get-Item -LiteralPath $path).Length
            sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    New-Item -ItemType Directory -Path $destination | Out-Null
    $archive = [IO.Compression.ZipFile]::Open($zipPath, 'Create')
    try {
        foreach ($record in $records) {
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, (Get-CheckedPath $record.path), $record.path,
                [IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally { $archive.Dispose() }
    [IO.File]::WriteAllText($manifestPath, (ConvertTo-Json -InputObject @($records) -Depth 4), [Text.UTF8Encoding]::new($false))
} else {
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Snapshot manifest missing.' }
    $records = @(Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json)
}
$archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    foreach ($record in $records) {
        $entry = $archive.GetEntry($record.path)
        if ($null -eq $entry) { throw "ZIP entry missing: $($record.path)" }
        $stream = $entry.Open()
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose(); $stream.Dispose() }
        if ($hash -ne $record.sha256) { throw "ZIP hash mismatch: $($record.path)" }
    }
} finally { $archive.Dispose() }
if ($RemoveRetired) {
    $paths = foreach ($relative in $retired) {
        $path = Get-CheckedPath $relative
        $record = @($records | Where-Object path -EQ $relative)
        if ($record.Count -ne 1 -or $record[0].action -ne 'retire_after_verification') { throw 'Manifest mismatch.' }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record[0].sha256) {
            throw "File changed since snapshot; refusing deletion: $relative"
        }
        $path
    }
    foreach ($path in $paths) { Remove-Item -LiteralPath $path }
    Write-Output "Removed $($paths.Count) explicitly listed obsolete plans; verified ZIP retained."
} else {
    Write-Output "Archived and SHA-256 verified $($records.Count) files: $zipPath"
}
