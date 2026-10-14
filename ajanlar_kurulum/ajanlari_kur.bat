@echo off
REM Proje ajanlarini .claude\agents klasorune kopyalar (Claude Code bu klasoru okur).
cd /d "%~dp0.."
if not exist ".claude\agents" mkdir ".claude\agents"
copy /Y "%~dp0*.md" ".claude\agents\" >nul
echo Ajanlar kuruldu: .claude\agents
dir /b ".claude\agents"
pause
