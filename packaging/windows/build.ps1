# Builds dist\BlindCue (PyInstaller) and dist\BlindCue-Setup-<version>.exe (Inno Setup).
#
# The version comes from blindcue\version.py (APP_VERSION) or, without that
# file, from pyproject.toml. The GitHub workflow
# .github\workflows\windows-installer.yml runs this same script.
#
# Requirements:
#   - Python 3.10+ on PATH (a build\venv is created on the first run)
#   - an FFmpeg build: the folder with ffmpeg.exe and ffprobe.exe
#   - Inno Setup 6 (ISCC.exe; found in its usual places, or pass -Iscc)
#
# From the repository root:
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -FfmpegDir C:\ffmpeg\bin

param(
    [Parameter(Mandatory = $true)][string]$FfmpegDir,
    [string]$Iscc = ""
)
$ErrorActionPreference = "Stop"
# A relative -FfmpegDir means relative to where the script was started.
$FfmpegDir = (Resolve-Path $FfmpegDir).Path
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

# ── Version ────────────────────────────────────────────────────────────────
$Version = $null
if (Test-Path "blindcue\version.py") {
    $m = Select-String -Path "blindcue\version.py" -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($m) { $Version = $m.Matches[0].Groups[1].Value }
}
if (-not $Version) {
    $m = Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $m) { throw "No version in blindcue\version.py or pyproject.toml" }
    $Version = $m.Matches[0].Groups[1].Value
}
# Numeric form for the Windows file properties: 0.1 -> 0.1.0.0
$nums = [regex]::Matches($Version, '\d+') | ForEach-Object { $_.Value }
$VersionNum = (($nums + @('0', '0', '0', '0'))[0..3]) -join '.'
Write-Host "Version: $Version ($VersionNum)"

# ── Inno Setup ─────────────────────────────────────────────────────────────
if (-not $Iscc) {
    $Iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc -or -not (Test-Path $Iscc)) { throw "ISCC.exe (Inno Setup 6) not found - pass -Iscc" }

# ── Python environment ─────────────────────────────────────────────────────
$venvPy = Join-Path $root "build\venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "[1/3] Creating build\venv..."
    python -m venv build\venv
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r requirements.txt pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

Write-Host "[2/3] PyInstaller..."
$env:BLINDCUE_FFMPEG_DIR = $FfmpegDir
& $venvPy -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi packaging\windows\blindcue.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "[3/3] Inno Setup..."
& $Iscc /Q "/DAppVersion=$Version" "/DAppVersionNum=$VersionNum" packaging\windows\BlindCue.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Get-Item "dist\BlindCue-Setup-$Version.exe" |
    Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
