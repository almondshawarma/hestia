@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Project Setup : %~dp0
echo ============================================================
echo.

:: ── Move into the repo directory (same folder as this script) ──────────────
cd /d "%~dp0"

:: ── Git LFS ────────────────────────────────────────────────────────────────
echo [1/4] Checking Git LFS...
where git-lfs >nul 2>&1
if %errorlevel% neq 0 (
    echo   WARNING: git-lfs not found. Install from https://git-lfs.github.com/
    echo   Skipping LFS init. STL and binary files will not be tracked correctly.
) else (
    git lfs install
    echo   Git LFS initialized.
)
echo.

:: ── Python check ──────────────────────────────────────────────────────────
echo [2/4] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python not found. Install from https://python.org/
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Found Python %PYVER%
echo.

:: ── Virtual environment ───────────────────────────────────────────────────
echo [3/4] Setting up virtual environment...
if exist "venv\" (
    echo   venv already exists, skipping creation.
) else (
    python -m venv venv
    echo   Created venv\
)

:: Activate and install
call venv\Scripts\activate.bat

if exist "requirements.txt" (
    echo   Installing from requirements.txt...
    pip install --upgrade pip --quiet
    pip install -r requirements.txt
    echo   Packages installed.
) else (
    echo   No requirements.txt found — installing defaults...
    pip install --upgrade pip --quiet
    pip install numpy scipy matplotlib pandas jupyter manim puresnmp pyserial
    pip freeze > requirements.txt
    echo   Default requirements.txt created.
)
echo.

:: ── 4. Done ──────────────────────────────────────────────────────────────────
echo [4/4] Setup complete.
echo.
echo   Activate venv:   venv\Scripts\activate
echo   Deactivate:      deactivate
echo   Freeze deps:     pip freeze ^> requirements.txt
echo.
echo   See setup.md for full reference.
echo ============================================================
pause