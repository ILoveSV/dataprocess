# ================================================
# start.ps1 - 极化带效应探测系统 启动脚本 (PowerShell)
# 用法: 在 PowerShell 中执行 .\start.ps1
# ================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$env:PYTHONPATH = $ScriptDir

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  极化带效应探测系统 - 正在启动..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Python 路径
$PythonExe = "D:\Anaconda\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python not found: $PythonExe" -ForegroundColor Red
    Write-Host "Check the Python path configured in this startup script." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Python: $PythonExe" -ForegroundColor Green

# 验证依赖
Write-Host "[Check] Verifying dependencies..." -ForegroundColor Yellow
$null = & $PythonExe -c "import PyQt5, numpy, scipy, pandas, nptdms, h5py, matplotlib" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Warn] Some deps missing, installing..." -ForegroundColor Yellow
    $null = & $PythonExe -m pip install nptdms h5py --quiet 2>$null
}
Write-Host "[OK] Dependencies ready" -ForegroundColor Green
Write-Host ""

# 启动主程序 (Stderr redirected to avoid Qt font warnings in PS)
Write-Host "[Start] Launching main program..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList "`"$ScriptDir\main.py`"" `
    -Wait -NoNewWindow -PassThru `
    -RedirectStandardError "$ScriptDir\stderr.log"

if ($proc.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "[ERROR] Program exited with code: $($proc.ExitCode)" -ForegroundColor Red
    Write-Host "================================================" -ForegroundColor Red
    Write-Host ""
    if (Test-Path "$ScriptDir\gui_debug.log") {
        Write-Host "--- gui_debug.log (last 20 lines) ---" -ForegroundColor Yellow
        Get-Content "$ScriptDir\gui_debug.log" -Tail 20
    }
    if (Test-Path "$ScriptDir\stderr.log") {
        $stderrContent = Get-Content "$ScriptDir\stderr.log" -Raw
        if ($stderrContent.Trim() -ne "") {
            Write-Host "--- stderr output ---" -ForegroundColor Yellow
            Write-Host $stderrContent
        }
    }
}

Read-Host "Press Enter to exit"
