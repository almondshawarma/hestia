#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo " Project Setup : $(dirname "$(realpath "$0")")"
echo "============================================================"
echo

# ── Move into the repo directory (same folder as this script) ──────────────
cd "$(dirname "$(realpath "$0")")"

# ── Git LFS ────────────────────────────────────────────────────────────────
echo "[1/5] Checking Git LFS..."
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

# ── macOS system libs for Manim (pycairo/manimpango have no prebuilt macOS ───
#    wheels, so pip compiles them from source and needs these on PATH first) ──
echo "[2/5] Checking Manim's system libraries (macOS)..."
if [[ "$(uname -s)" == "Darwin" ]]; then
    MANIM_DEPS=(cairo pkg-config pango ffmpeg)
    MISSING=()
    for dep in "${MANIM_DEPS[@]}"; do
        brew list --versions "$dep" &>/dev/null || MISSING+=("$dep")
    done

    if [ ${#MISSING[@]} -eq 0 ]; then
        echo "  cairo, pkg-config, pango, ffmpeg already present."
    elif command -v brew &>/dev/null; then
        echo "  Installing missing deps via Homebrew: ${MISSING[*]}"
        brew install "${MISSING[@]}"
        echo "  Done."
    else
        echo "  ERROR: Homebrew not found, and these are missing: ${MISSING[*]}"
        echo "    Install Homebrew first: https://brew.sh"
        echo "    Then:  brew install ${MISSING[*]}"
        echo "    (Without these, 'pip install manim' fails building pycairo from source.)"
        exit 1
    fi
else
    echo "  Not macOS, skipping (Linux: apt install pkg-config libcairo2-dev libpango1.0-dev ffmpeg)."
fi
echo

# ── Python check (require 3.12 or 3.13) ──────────────────────────────────────
echo "[3/5] Checking Python (need 3.12 or 3.13)..."

# Prefer the newest supported interpreter; the venv permanently inherits whichever
# one creates it, so picking the right python here pins the whole environment.
PYTHON=""
for cand in python3.13 python3.12 python3 python; do
    if command -v "$cand" &>/dev/null && \
       "$cand" -c 'import sys; raise SystemExit(0 if (3,12)<=sys.version_info[:2]<(3,14) else 1)' 2>/dev/null; then
        PYTHON="$cand"; break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ERROR: need Python 3.12 or 3.13, none found on PATH."
    echo "    macOS:   brew install python@3.12    (or python.org 3.12.x/3.13.x installer)"
    echo "    Ubuntu:  sudo apt install python3.12 python3.12-venv"
    echo "    then re-run ./setup.sh"
    exit 1
fi

PYVER=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "  Using $PYTHON ($PYVER)"
echo

# ── Virtual environment ────────────────────────────────────────────────────
echo "[4/5] Setting up virtual environment..."

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
echo "[5/5] Setup complete."
echo
echo "  Activate venv:   source venv/bin/activate"
echo "  Deactivate:      deactivate"
echo "  Freeze deps:     pip freeze > requirements.txt"
echo
echo "  See setup.md for full reference."
echo "============================================================"
