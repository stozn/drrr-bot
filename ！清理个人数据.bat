@echo off
chcp 65001 > nul

if exist "config.txt" (
    del "config.txt"
)

if exist "logs" (
    rmdir "logs" /S /Q
)

if exist "cookies" (
    rmdir "cookies" /S /Q
)

echo All Cleaned
pause
