#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo " Project Setup : $(dirname "$(realpath "$0")")"
echo "============================================================"
echo

# ── Move into the repo directory (same folder as this script) ──────────────
cd "$(dirname "$(realpath "$0")")"

# ── Git LFS ────────────────────────────────────────────────────────────────
echo "[1/4] Checking Git LFS..."
if ! command -v git-lfs &>/dev/null; then
    echo "  WARNING: git-lfs not found."
    echo "  Install: sudo apt install git-lfs  (Ubuntu)"
    echo "           brew install git-lfs       (macOS)"
    echo "  Skipping LFS init. STL and binary files will not be tracked correctly."
else
    git lfs install
    echo "  Git LFS initialized."
fi
echo

# ── Python check ───────────────────────────────────────────────────────────
echo "[2/4] Checking Python..."

# Prefer python3, fall back to python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  ERROR: Python not found. Install from https://python.org/"
    exit 1
fi

PYVER=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "  Found $PYTHON $PYVER"
echo

# ── Virtual environment ────────────────────────────────────────────────────
echo "[3/4] Setting up virtual environment..."

if [ -d "venv" ]; then
    echo "  venv already exists, skipping creation."
else
    $PYTHON -m venv venv
    echo "  Created venv/"
fi

# shellcheck source=/dev/null
source venv/bin/activate

if [ -f "requirements.txt" ]; then
    echo "  Installing from requirements.txt..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt
    echo "  Packages installed."
else
    echo "  No requirements.txt found, installing defaults..."
    pip install --upgrade pip --quiet
    pip install numpy scipy matplotlib pandas jupyter manim puresnmp pyserial
    pip freeze > requirements.txt
    echo "  Default requirements.txt created."
fi
echo

# ── Done ───────────────────────────────────────────────────────────────────
echo "[4/4] Setup complete."
echo
echo "  Activate venv:   source venv/bin/activate"
echo "  Deactivate:      deactivate"
echo "  Freeze deps:     pip freeze > requirements.txt"
echo
echo "  See setup.md for full reference."
echo "============================================================"
