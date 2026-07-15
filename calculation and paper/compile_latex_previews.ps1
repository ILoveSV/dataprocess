$ErrorActionPreference = "Stop"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

function Invoke-XeLaTeX {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$MainFile,
        [string]$OutputDirectory = "build"
    )

    Push-Location -LiteralPath $WorkingDirectory
    try {
        New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
        $args = @(
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory=$OutputDirectory",
            $MainFile
        )
        & xelatex @args
        & xelatex @args
    }
    finally {
        Pop-Location
    }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Invoke-XeLaTeX -WorkingDirectory $root -MainFile "main.tex"
Invoke-XeLaTeX -WorkingDirectory (Join-Path $root "paper") -MainFile "main.tex"
Invoke-XeLaTeX -WorkingDirectory (Join-Path $root "ship_efield_theory\report") -MainFile "theory_derivation.tex"

Write-Host "PDF previews generated:"
Write-Host " - $(Join-Path $root 'build\main.pdf')"
Write-Host " - $(Join-Path $root 'paper\build\main.pdf')"
Write-Host " - $(Join-Path $root 'ship_efield_theory\report\build\theory_derivation.pdf')"
