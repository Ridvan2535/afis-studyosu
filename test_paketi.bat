@echo off
chcp 65001 >nul
cd /d "%~dp0"
python test_paketi.py %*
if errorlevel 1 python -X utf8 test_paketi.py %*
echo.
start "" "isler"
pause
