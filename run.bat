@echo off
REM ==============================================================================
REM  BlindCue — Launcher per Windows
REM ==============================================================================

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python blindcue\main.py %*
