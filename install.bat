@echo off
REM ==============================================================================
REM  BlindCue — Setup e Installazione Automatica per Windows (10 / 11)
REM ==============================================================================

echo.
echo ======================================================================
echo          BlindCue - Live Multimedia Cue Player (Windows Setup)
echo ======================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Python non e installato o non e presente nella variabile PATH.
    echo Scarica e installa Python 3.10+ da https://www.python.org/
    echo Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    echo.
    pause
    exit /b 1
)

echo [1/3] Creazione ambiente virtuale isolato (.venv)...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/3] Attivazione ambiente e aggiornamento pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet

echo [3/3] Installazione dipendenze (PySide6, NumPy)...
pip install -r requirements.txt

echo.
echo ======================================================================
echo    [OK] Installazione completata con successo per Windows!
echo    Per avviare BlindCue fai doppio click su: run.bat
echo ======================================================================
echo.
pause

