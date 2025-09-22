@echo off
setlocal enabledelayedexpansion

:: 初始化计数器
set "tdmsCounter=1"
set "indexCounter=1"

:: 处理当前目录中的 .tdms 文件
for /f "tokens=*" %%f in ('dir /b *.tdms') do (
    :: 格式化计数器为三位数
    set "formattedCounter=00!tdmsCounter!"
    set "formattedCounter=!formattedCounter:~-3!"
    
    :: 构建新文件名
    set "newName=1_250_1_!formattedCounter!.tdms"
    
    :: 重命名文件
    ren "%%f" "!newName!"
    
    :: 递增计数器
    set /a tdmsCounter+=1
)

:: 处理当前目录中的 .tdms_index 文件
for /f "tokens=*" %%f in ('dir /b *.tdms_index') do (
    :: 格式化计数器为三位数
    set "formattedCounter=00!indexCounter!"
    set "formattedCounter=!formattedCounter:~-3!"
    
    :: 构建新文件名
    set "newName=1_250_1_!formattedCounter!.tdms_index"
    
    :: 重命名文件
    ren "%%f" "!newName!"
    
    :: 递增计数器
    set /a indexCounter+=1
)

echo File renaming complete.
pause