@echo off
setlocal EnableExtensions
REM ==============================================================================
REM  BlindCue - Launcher per Windows
REM ==============================================================================

REM Lavora sempre nella cartella dello script, anche se lanciato da un altro percorso
cd /d "%~dp0"

REM UTF-8: evita errori di codifica sui log (e sui nomi file con accenti)
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRORE] Ambiente di sviluppo non configurato.
    echo.
    echo   Per installare BlindCue:   python setup.py
    echo   Per lo sviluppo:           python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" blindcue\main.py %*
if errorlevel 1 (
    echo.
    echo [ERRORE] BlindCue e terminato con un errore: copia il messaggio sopra.
    echo         Per maggiori dettagli riavvia con: run.bat --debug
    echo.
    pause
)
