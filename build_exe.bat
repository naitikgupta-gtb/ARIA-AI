@echo off
REM Builds ARIA into a Windows .exe using PyInstaller.
REM Run this from inside the aria_app folder, in an activated venv
REM where requirements.txt is already installed.
REM
REM This just runs ARIA.spec — do NOT duplicate its flags here.
REM ARIA.spec is the single source of truth for what gets bundled
REM (this previously had its own separate, out-of-date flag list that
REM was missing the entire modules/ folder and config.py — meaning a
REM build from that old version silently shipped an exe with most of
REM ARIA's tools missing. If you add a new module under modules/ or a
REM new third-party package, update ARIA.spec, not this file.)

pyinstaller --noconfirm ARIA.spec

echo.
echo Build finished. Find ARIA.exe in dist\ARIA.exe
echo Reminder: end users still need their own Gemini API key entered
echo via Settings in the app — see README_SELL.md.
pause
