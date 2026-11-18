param([switch]$SkipChecks)
$ErrorActionPreference = 'Stop'
$modelRoot = $PSScriptRoot
$comsolBin = 'D:\COMSOL64\Multiphysics\bin\win64'
$pdfPython = 'C:\Users\17584\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$plotPython = 'D:\Anaconda\python.exe'
Push-Location -LiteralPath $modelRoot
try {
    & $pdfPython -X utf8 (Join-Path $modelRoot 'extract_polarization.py')
    if ($LASTEXITCODE -ne 0) { throw 'Polarization extraction failed.' }
    $sources = @('ICCPInputs', 'SubmarineICCP', 'SubmarineICCPFine', 'SubmarineICCPWide')
    foreach ($source in $sources) {
        $compileStart = Get-Date
        & (Join-Path $comsolBin 'comsolcompile.exe') -classpathadd $modelRoot "$source.java"
        $compiled = Get-Item -LiteralPath "$source.class" -ErrorAction Stop
        if ($compiled.LastWriteTime -lt $compileStart.AddSeconds(-1)) { throw "Compilation did not update $source.class" }
    }
    $currentLine = Get-Content -LiteralPath 'parameters.properties' | Where-Object { $_ -match '^I_total=' }
    $nominal = [double](($currentLine -split '=')[1] -replace '\[A\]','')
    $nominalTag = $nominal.ToString('G', [cultureinfo]::InvariantCulture)
    $highTag = (2*$nominal).ToString('G', [cultureinfo]::InvariantCulture)
    $jobs = @(@{Name='base'; Class='SubmarineICCP'; Expected="base_${highTag}A"})
    if (-not $SkipChecks) {
        $jobs += @{Name='fine'; Class='SubmarineICCPFine'; Expected="fine_${nominalTag}A"}
        $jobs += @{Name='wide'; Class='SubmarineICCPWide'; Expected="wide_${nominalTag}A"}
    }
    foreach ($job in $jobs) {
        $started = Get-Date
        & (Join-Path $comsolBin 'comsolbatch.exe') -np 4 -graphics -3drend sw -classpathadd $modelRoot -inputfile "$($job.Class).class" -batchlog "$($job.Name).log"
        $logText = Get-Content -LiteralPath "$($job.Name).log" -Raw
        if ($logText.Contains('运行 Java 类时出错') -or $logText.Contains('/*****错误')) { throw "COMSOL failed; see $($job.Name).log" }
        $saved = Get-Item -LiteralPath "models/submarine_iccp_$($job.Expected).mph"
        if ($saved.LastWriteTime -lt $started) { throw "Missing fresh output: $($job.Expected)" }
    }
    $postArgs = @('-X', 'utf8', (Join-Path $modelRoot 'summarize_results.py'))
    if ($SkipChecks) { $postArgs += '--base-only' }
    & $plotPython @postArgs
    if ($LASTEXITCODE -ne 0) { throw 'Postprocessing failed.' }
    & $plotPython -X utf8 (Join-Path $modelRoot 'validate_results.py')
    if ($LASTEXITCODE -ne 0) { throw 'Consistency validation failed.' }
} finally {
    Pop-Location
}
