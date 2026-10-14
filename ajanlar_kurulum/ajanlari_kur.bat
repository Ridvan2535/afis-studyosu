@echo off
REM Proje ajanlarini .claude\agents klasorune kopyalar (Claude Code bu klasoru okur).
REM OKUBENI.md ve eski image-engineer.md (K-57 ile kaldirildi) KOPYALANMAZ.
cd /d "%~dp0.."
if not exist ".claude\agents" mkdir ".claude\agents"
for %%F in ("%~dp0*.md") do (
  if /I not "%%~nxF"=="OKUBENI.md" if /I not "%%~nxF"=="image-engineer.md" copy /Y "%%F" ".claude\agents\" >nul
)
if exist ".claude\agents\image-engineer.md" del ".claude\agents\image-engineer.md"
if exist ".claude\agents\OKUBENI.md" del ".claude\agents\OKUBENI.md"
echo Ajanlar kuruldu: .claude\agents
dir /b ".claude\agents"
pause
