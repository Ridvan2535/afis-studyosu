@echo off
setlocal
cd /d "%~dp0"
title Afis Studyosu - Kurulum
chcp 65001 >nul
set PYTHONUTF8=1
echo.
echo ===========================================
echo   Afis Studyosu - ilk kurulum
echo ===========================================
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo HATA: Uygun bir Python bulunamadi ^(3.10 veya daha yenisi gerekli^).
  echo.
  echo 1^) https://www.python.org/downloads/ adresinden Python 3.12 indir.
  echo 2^) Kurulum ekraninda EN ALTTAKI "Add python.exe to PATH" kutusunu ISARETLE.
  echo 3^) Kurulum bitince bu dosyaya tekrar cift tikla.
  echo.
  pause
  exit /b 1
)
echo Python bulundu: %PY%
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Program icin ayri bir ortam hazirlaniyor...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo HATA: Ortam olusturulamadi. Bu ekrani bana gonder.
    pause
    exit /b 1
  )
)

echo Gerekli paketler indiriliyor. Internet gerekir, birkac dakika surebilir...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo HATA: Paketler kurulamadi. Internet baglantisini kontrol edip tekrar dene.
  echo Yine olmazsa bu ekranin fotografini bana gonder.
  pause
  exit /b 1
)

echo.
echo Kurulum denetleniyor...
".venv\Scripts\python.exe" kontrol.py
if errorlevel 1 (
  echo.
  echo Denetimde sorun cikti. Bu ekranin fotografini bana gonder.
  pause
  exit /b 1
)

echo.
echo ===========================================
echo   Kurulum bitti. Simdi baslat.bat dosyasina cift tikla.
echo ===========================================
pause
