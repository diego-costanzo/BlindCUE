@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ==============================================================================
REM  BlindCue - Installer per Windows 10 / 11
REM
REM  Installa in:  %LOCALAPPDATA%\Programs\BlindCue   (nessun permesso admin)
REM  Crea:         collegamento sul Desktop e nel menu Start (icona BlindCue)
REM
REM  Uso:
REM    setup\windows\install.bat            installazione interattiva
REM    setup\windows\install.bat /yes       senza domande (per la finestra grafica)
REM    setup\windows\install.bat /check     solo controlli, non installa nulla
REM
REM  Le righe "[STEP] n/6 ..." permettono alla GUI di mostrare l'avanzamento.
REM ==============================================================================

if "%~1"=="" goto :args_done
set "ASSUME_YES=0"
set "CHECK_ONLY=0"
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="/yes" set "ASSUME_YES=1"
if /I "%~1"=="-y" set "ASSUME_YES=1"
if /I "%~1"=="/check" set "CHECK_ONLY=1"
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~1"=="/?" goto :usage
shift
goto :parse_args

:usage
echo Uso: setup\windows\install.bat [/yes] [/check]
exit /b 0

:args_done
if not defined ASSUME_YES set "ASSUME_YES=0"
if not defined CHECK_ONLY set "CHECK_ONLY=0"
set "FAILED=0"

chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "REPO_ROOT=%~dp0..\.."
pushd "%REPO_ROOT%"
set "REPO_ROOT=%CD%"
popd

if defined BLINDCUE_PREFIX (
    set "INSTALL_DIR=%BLINDCUE_PREFIX%"
) else (
    set "INSTALL_DIR=%LOCALAPPDATA%\Programs\BlindCue"
)
set "APP_DIR=%INSTALL_DIR%\app"
set "VENV_DIR=%INSTALL_DIR%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"
set "ICON_SRC=%REPO_ROOT%\setup\assets\blindcue.ico"
set "ICON_DST=%INSTALL_DIR%\BlindCue.ico"

echo.
echo ======================================================================
echo        BlindCue - Installazione per Windows (utente corrente)
echo ======================================================================
echo.

REM ------------------------------------------------------------------------------
REM [STEP] 1/6 - Controlli preliminari
REM ------------------------------------------------------------------------------
echo [STEP] 1/6 Controlli preliminari

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [FAIL] Python non trovato nel PATH.
        echo        Scarica Python 3.10+ da https://www.python.org/downloads/
        echo        Durante l'installazione spunta "Add python.exe to PATH".
        set "FAILED=1"
        goto :report
    )
    set "PY=py -3"
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do echo [FAIL] Python %%v troppo vecchio: serve 3.10 o superiore.
    set "FAILED=1"
    goto :report
)
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do echo [ OK ] Python %%v

set "RAM_MB=0"
for /f "usebackq delims=" %%r in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1MB)"`) do set "RAM_MB=%%r"
echo [INFO] RAM totale: !RAM_MB! MB
if !RAM_MB! LSS 2048 echo [WARN] RAM limitata: BlindCue usara automaticamente il profilo ECO.

set "FREE_MB=0"
for /f "usebackq delims=" %%f in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[math]::Round((Get-PSDrive C).Free/1MB)"`) do set "FREE_MB=%%f"
echo [INFO] Spazio libero su C: !FREE_MB! MB
if !FREE_MB! LSS 1500 (
    echo [FAIL] Servono almeno 1.5 GB liberi per PySide6.
    set "FAILED=1"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Method Head -Uri 'https://pypi.org/pypi/PySide6/json' -TimeoutSec 8; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
    if exist "%VENV_PY%" (
        echo [WARN] pypi.org non raggiungibile, ma l'ambiente virtuale esiste gia: continuo.
    ) else (
        echo [FAIL] Nessun accesso a pypi.org: impossibile scaricare le dipendenze.
        set "FAILED=1"
    )
) else (
    echo [ OK ] Accesso a pypi.org disponibile
)

set "GPU_NAME="
for /f "usebackq delims=" %%g in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-CimInstance Win32_VideoController).Name -join ', '"`) do set "GPU_NAME=%%g"
if defined GPU_NAME echo [INFO] GPU rilevata: !GPU_NAME!

REM ------------------------------------------------------------------------------
REM [STEP] 2/6 - FFmpeg / FFprobe
REM ------------------------------------------------------------------------------
echo [STEP] 2/6 Componenti di sistema
set "HAS_FFMPEG=1"
where ffmpeg >nul 2>nul || set "HAS_FFMPEG=0"
where ffprobe >nul 2>nul || set "HAS_FFMPEG=0"

if "%HAS_FFMPEG%"=="1" (
    echo [ OK ] FFmpeg e FFprobe trovati nel PATH
) else (
    echo [WARN] FFmpeg / FFprobe non trovati: forma d'onda, loudness e
    echo        normalizzazione audio sarebbero disabilitate.
    if "%CHECK_ONLY%"=="0" (
        where winget >nul 2>nul
        if errorlevel 1 (
            echo [FAIL] winget non disponibile. Installa FFmpeg manualmente:
            echo        https://ffmpeg.org/download.html
            echo        Poi riapri il prompt dei comandi.
            set "FAILED=1"
        ) else (
            if "%ASSUME_YES%"=="0" (
                set /p "ANSWER=Installare FFmpeg adesso tramite winget? [S/n] "
                if /I "!ANSWER!"=="n" goto :skip_ffmpeg
            )
            echo [INFO] Installazione FFmpeg tramite winget...
            winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements --silent
            if errorlevel 1 (
                echo [FAIL] Installazione FFmpeg non riuscita.
                set "FAILED=1"
            ) else (
                echo [ OK ] FFmpeg installato. Potrebbe servire riaprire il terminale.
            )
        )
    )
)
:skip_ffmpeg

:report
if "%CHECK_ONLY%"=="1" goto :check_report
if "%FAILED%"=="1" (
    echo.
    echo [FAIL] Impossibile continuare: mancano prerequisiti obbligatori.
    exit /b 1
)

if "%ASSUME_YES%"=="0" (
    set /p "ANSWER=BlindCue verra installato in !INSTALL_DIR!. Procedo? [S/n] "
    if /I "!ANSWER!"=="n" (
        echo Installazione annullata.
        exit /b 0
    )
)

REM ------------------------------------------------------------------------------
REM [STEP] 3/6 - Copia dei file
REM ------------------------------------------------------------------------------
echo [STEP] 3/6 Copia dei file in !INSTALL_DIR!
if not exist "%REPO_ROOT%\blindcue\main.py" (
    echo [FAIL] File del programma non trovati in %REPO_ROOT%\blindcue
    exit /b 1
)

if not exist "%APP_DIR%" mkdir "%APP_DIR%" >nul 2>nul
if exist "%APP_DIR%\blindcue" rmdir /S /Q "%APP_DIR%\blindcue"
robocopy "%REPO_ROOT%\blindcue" "%APP_DIR%\blindcue" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo [FAIL] Copia dei file non riuscita.
    exit /b 1
)
copy /Y "%REPO_ROOT%\requirements.txt" "%APP_DIR%\requirements.txt" >nul
if exist "%REPO_ROOT%\LICENSE" copy /Y "%REPO_ROOT%\LICENSE" "%APP_DIR%\LICENSE" >nul
if exist "%REPO_ROOT%\README.md" copy /Y "%REPO_ROOT%\README.md" "%APP_DIR%\README.md" >nul
if exist "%REPO_ROOT%\docs" robocopy "%REPO_ROOT%\docs" "%APP_DIR%\docs" /E /NFL /NDL /NJH /NJS /NP >nul
if exist "%ICON_SRC%" copy /Y "%ICON_SRC%" "%ICON_DST%" >nul
echo [ OK ] Programma copiato in %APP_DIR%

REM ------------------------------------------------------------------------------
REM [STEP] 4/6 - Ambiente virtuale e dipendenze
REM ------------------------------------------------------------------------------
echo [STEP] 4/6 Ambiente Python e dipendenze
if not exist "%VENV_PY%" (
    echo [INFO] Creazione ambiente virtuale in %VENV_DIR% ...
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [FAIL] Creazione ambiente virtuale non riuscita.
        exit /b 1
    )
) else (
    echo [INFO] Ambiente virtuale esistente riutilizzato
)

"%VENV_PY%" -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 (
    echo [FAIL] Aggiornamento pip non riuscito.
    exit /b 1
)
echo [INFO] Installazione dipendenze Python (puo richiedere qualche minuto) ...
"%VENV_PY%" -m pip install -r "%APP_DIR%\requirements.txt"
if errorlevel 1 (
    echo [FAIL] Installazione dipendenze non riuscita. Verifica la connessione internet.
    exit /b 1
)
echo [ OK ] Dipendenze Python installate

REM ------------------------------------------------------------------------------
REM [STEP] 5/6 - Verifica
REM ------------------------------------------------------------------------------
echo [STEP] 5/6 Verifica dell'installazione
"%VENV_PY%" -c "import PySide6, numpy; from PySide6.QtMultimedia import QMediaPlayer; print('  [OK] PySide6 / QtMultimedia / NumPy')"
if errorlevel 1 (
    echo [FAIL] Moduli Python non funzionanti.
    exit /b 1
)

set "QT_QPA_PLATFORM=offscreen"
pushd "%APP_DIR%\blindcue"
"%VENV_PY%" -c "import sys; sys.path.insert(0,'.'); from PySide6.QtWidgets import QApplication; app=QApplication(sys.argv); import engine.audio_analyzer, engine.player_live, engine.player_test, models.project_manager, services.osc_server, services.web_server, ui.main_window, ui.output_window; print('  [OK] Tutti i moduli BlindCue importati correttamente')"
if errorlevel 1 (
    popd
    echo [FAIL] L'applicazione non e riuscita a importare i propri moduli.
    exit /b 1
)
popd
set "QT_QPA_PLATFORM="
echo [ OK ] Verifica completata

REM ------------------------------------------------------------------------------
REM [STEP] 6/6 - Lanciatore e collegamenti
REM ------------------------------------------------------------------------------
echo [STEP] 6/6 Lanciatore e collegamenti

REM run.bat: avvio da terminale (mostra eventuali errori).
> "%INSTALL_DIR%\run.bat" (
    echo @echo off
    echo setlocal
    echo set "LC_NUMERIC=C"
    echo "%%~dp0venv\Scripts\python.exe" "%%~dp0app\blindcue\main.py" %%*
)

REM ------------------------------------------------------------------------------
REM Disinstallatore autonomo: sta FUORI dalla cartella del programma, cosi puo
REM cancellarla mentre e in esecuzione. Il repository puo essere eliminato.
REM ------------------------------------------------------------------------------
for %%I in ("%INSTALL_DIR%\..") do (
    set "UNINSTALL_DIR=%%~fI"
    set "UNINSTALL_BAT=%%~fI\BlindCue-uninstall.bat"
)

> "%UNINSTALL_BAT%" echo @echo off
>>"%UNINSTALL_BAT%" echo setlocal EnableExtensions
>>"%UNINSTALL_BAT%" echo chcp 65001 ^>nul 2^>nul
>>"%UNINSTALL_BAT%" echo title BlindCue - Disinstallazione
>>"%UNINSTALL_BAT%" echo echo BlindCue verra rimosso da: %INSTALL_DIR%
>>"%UNINSTALL_BAT%" echo echo I tuoi progetti .blindcue non vengono toccati.
>>"%UNINSTALL_BAT%" echo echo.
>>"%UNINSTALL_BAT%" echo choice /C SN /N /M "Rimuovere BlindCue da questo computer? [S/N] "
>>"%UNINSTALL_BAT%" echo if errorlevel 2 goto :cancelled
>>"%UNINSTALL_BAT%" echo set "PURGE=0"
>>"%UNINSTALL_BAT%" echo choice /C SN /N /M "Rimuovere anche impostazioni e autosave? [S/N] "
>>"%UNINSTALL_BAT%" echo if not errorlevel 2 set "PURGE=1"
>>"%UNINSTALL_BAT%" echo if exist "%USERPROFILE%\Desktop\BlindCue.lnk" del /f /q "%USERPROFILE%\Desktop\BlindCue.lnk"
>>"%UNINSTALL_BAT%" echo if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\BlindCue.lnk" del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\BlindCue.lnk"
>>"%UNINSTALL_BAT%" echo if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Uninstall BlindCue.lnk" del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Uninstall BlindCue.lnk"
if defined OneDrive >>"%UNINSTALL_BAT%" echo if exist "%OneDrive%\Desktop\BlindCue.lnk" del /f /q "%OneDrive%\Desktop\BlindCue.lnk"
>>"%UNINSTALL_BAT%" echo if "%PURGE%"=="1" if exist "%APPDATA%\BlindCue" rmdir /s /q "%APPDATA%\BlindCue"
>>"%UNINSTALL_BAT%" echo if "%PURGE%"=="1" reg delete "HKCU\Software\BlindCue" /f ^>nul 2^>nul
>>"%UNINSTALL_BAT%" echo echo.
>>"%UNINSTALL_BAT%" echo echo Rimozione del programma in corso ...
>>"%UNINSTALL_BAT%" echo rmdir /s /q "%INSTALL_DIR%"
>>"%UNINSTALL_BAT%" echo echo.
>>"%UNINSTALL_BAT%" echo echo BlindCue e stato rimosso.
>>"%UNINSTALL_BAT%" echo if exist "%ICON_DST%" del /f /q "%ICON_DST%"
>>"%UNINSTALL_BAT%" echo (goto) 2^>nul ^& del "%UNINSTALL_BAT%" ^& exit /b 0
>>"%UNINSTALL_BAT%" echo :cancelled
>>"%UNINSTALL_BAT%" echo echo Operazione annullata.
>>"%UNINSTALL_BAT%" echo exit /b 0
echo [ OK ] Disinstallatore creato: %UNINSTALL_BAT%

REM Collegamenti: pythonw.exe = nessuna finestra di terminale.
set "TARGET=%VENV_PYW%"
if not exist "%TARGET%" set "TARGET=%VENV_PY%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell); $dirs=@([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')); foreach($d in $dirs){ if(-not (Test-Path $d)){ continue }; $l=$s.CreateShortcut((Join-Path $d 'BlindCue.lnk')); $l.TargetPath='%TARGET%'; $l.Arguments=([char]34 + '%APP_DIR%\blindcue\main.py' + [char]34); $l.WorkingDirectory='%APP_DIR%'; $l.IconLocation='%ICON_DST%,0'; $l.Description='BlindCue - Live Cue Player'; $l.Save() }"
if errorlevel 1 (
    echo [WARN] Creazione dei collegamenti non riuscita: usa "%INSTALL_DIR%\run.bat".
) else (
    echo [ OK ] Collegamenti creati su Desktop e menu Start
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell); $d=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'; if (Test-Path $d) { $l=$s.CreateShortcut((Join-Path $d 'Uninstall BlindCue.lnk')); $l.TargetPath='%UNINSTALL_BAT%'; $l.WorkingDirectory='%UNINSTALL_DIR%'; $l.IconLocation='%ICON_DST%,0'; $l.Description='Rimuove BlindCue'; $l.Save() }" >nul 2>nul

echo.
echo ======================================================================
echo    [OK] BlindCue installato correttamente
echo    Cartella: %INSTALL_DIR%
echo    Avvio: icona BlindCue sul Desktop o nel menu Start
echo    Diagnostica: "%INSTALL_DIR%\run.bat" --debug
echo    Disinstallazione: "%UNINSTALL_BAT%" (o "Uninstall BlindCue" nel menu Start)
echo ======================================================================
echo.
exit /b 0

:check_report
echo.
if "%FAILED%"=="1" (
    echo [FAIL] Controlli completati con problemi - vedi sopra.
    exit /b 1
)
echo [ OK ] Controlli completati: il sistema e pronto per BlindCue.
echo        Esegui install.bat senza /check per completare l'installazione.
exit /b 0
