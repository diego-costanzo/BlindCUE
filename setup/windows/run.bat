@echo off
setlocal
REM ==============================================================================
REM  BlindCue - avvio su Windows
REM
REM  Usa l'installazione in %LOCALAPPDATA%\Programs\BlindCue.
REM  Se non e ancora installata, spiega come fare invece di fallire in silenzio.
REM ==============================================================================

if defined BLINDCUE_PREFIX (
    set "INSTALL_DIR=%BLINDCUE_PREFIX%"
) else (
    set "INSTALL_DIR=%LOCALAPPDATA%\Programs\BlindCue"
)

if not exist "%INSTALL_DIR%\run.bat" (
    echo BlindCue non risulta installato in: %INSTALL_DIR%
    echo.
    echo Per installarlo esegui: python "%~dp0..\..\setup.py"
    echo oppure: setup\windows\install.bat
    echo.
    pause
    exit /b 1
)

set "LC_NUMERIC=C"
call "%INSTALL_DIR%\run.bat" %*
