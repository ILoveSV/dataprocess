param(
    [string]$RawInput = "D:\Lab\raw\44.6.9\vac",
    [string]$ProcessOutput = "D:\Lab\process\44.6.9\vac\time",
    [string]$AnalysisOutput = "D:\Lab\results\44.6.9\vac\first_test_pipeline_44_6_9_vac_first3",
    [string]$RunId = $(Get-Date -Format "yyyyMMdd_HHmmss")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogRoot = Join-Path $RepoRoot ("logs\vac_first3_" + $RunId)
$RunLog = Join-Path $LogRoot "run.log"
$StatusFile = Join-Path $LogRoot "status.txt"

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
Set-Location $RepoRoot

function Write-RunLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $RunLog -Append
}

function Write-Status {
    param([string]$Message)
    $Message | Set-Content -Path $StatusFile -Encoding UTF8
    Write-RunLog ("STATUS " + $Message)
}

function Invoke-PythonStep {
    param(
        [string]$StepName,
        [string[]]$Arguments
    )

    Write-Status ("RUNNING " + $StepName)
    Write-RunLog ("COMMAND python " + ($Arguments -join " "))
    & python @Arguments 2>&1 | ForEach-Object {
        $_ | Tee-Object -FilePath $RunLog -Append
    }
    $exitCode = $LASTEXITCODE
    Write-RunLog ("EXIT " + $StepName + " code=" + $exitCode)
    if ($exitCode -ne 0) {
        Write-Status ("FAILED " + $StepName + " code=" + $exitCode)
        exit $exitCode
    }
}

Write-Status "STARTED"
Write-RunLog ("RepoRoot=" + $RepoRoot)
Write-RunLog ("RawInput=" + $RawInput)
Write-RunLog ("ProcessOutput=" + $ProcessOutput)
Write-RunLog ("AnalysisOutput=" + $AnalysisOutput)
Write-RunLog "Plan: convert merged TDMS to first 3 process CSV segments per TDMS, then run first-test-pipeline for every group. No background/bandpower gain step."

Invoke-PythonStep "merged_tdms_to_time_first3" @(
    "-m", "src.pipelines.merged_tdms_to_time_pipeline",
    "--input", $RawInput,
    "--output", $ProcessOutput,
    "--segment-seconds", "2.7",
    "--max-segments-per-file", "3",
    "--max-workers", "1"
)

if (Test-Path $ProcessOutput) {
    $csvCount = (Get-ChildItem $ProcessOutput -Recurse -Filter "*.csv" -File | Measure-Object).Count
    $jsonCount = (Get-ChildItem $ProcessOutput -Recurse -Filter "*.json" -File | Measure-Object).Count
    Write-RunLog ("ProcessOutput csv_count=" + $csvCount + " json_count=" + $jsonCount)
}

Invoke-PythonStep "first_test_pipeline_vac_first3" @(
    "-m", "src.main",
    "first-test-pipeline",
    "--input", $ProcessOutput,
    "--output", $AnalysisOutput,
    "--max-files", "3",
    "--skip-bandpower-gain"
)

if (Test-Path $AnalysisOutput) {
    $figureIndex = Join-Path $AnalysisOutput "figure_index.csv"
    $manifest = Join-Path $AnalysisOutput "first_test_manifest.json"
    Write-RunLog ("AnalysisOutput exists=" + (Test-Path $AnalysisOutput))
    Write-RunLog ("FigureIndex exists=" + (Test-Path $figureIndex))
    Write-RunLog ("Manifest exists=" + (Test-Path $manifest))
}

Write-Status "COMPLETED"
Write-RunLog "DONE"
