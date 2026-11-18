@echo off
title Signal Processor - TC12/TC34

set PYTHONPATH=%~dp0
set PYTHON_EXE=D:\Anaconda\python.exe

if exist "%PYTHON_EXE%" goto :run

echo [ERROR] Python not found: %PYTHON_EXE%
echo Check the Python path configured in this startup script.
pause
exit /b 1

:run
"%PYTHON_EXE%" "%~dp0main.py"
pause
