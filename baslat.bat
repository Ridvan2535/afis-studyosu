@echo off
setlocal
cd /d "%~dp0"
title Afis Studyosu
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo Program henuz kurulmamis. Once kur.bat dosyasina cift tikla.
  echo.
  pause
  exit /b 1
)
echo Afis Studyosu aciliyor. Tarayici kendiliginden acilacak.
echo Bu siyah pencere programin calistigi yerdir: calisirken KAPATMA.
echo.
".venv\Scripts\python.exe" app.py
echo.
echo Program kapandi. Bir hata yazisi gorduysen kopyalayip bana gonder.
pause
