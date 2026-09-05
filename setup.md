# Project Setup

A quick reference for spinning up a new project repo from this template.

---

## Prerequisites

Make sure these are installed before running the setup script:

- **Python 3.12 or 3.13** (not 3.14+, not 3.11-) : [python.org](https://www.python.org/downloads/)
- **Git** : [git-scm.com](https://git-scm.com/)
- **Git LFS** : [git-lfs.github.com](https://git-lfs.github.com/) (for STL/binary files)
- **Manim's native libs** (`cairo`, `pkg-config`, `pango`, `ffmpeg`) : pycairo/manimpango have no
  prebuilt wheels on macOS, so pip compiles them from source and needs these on `PATH` first, or
  `pip install -r requirements.txt` fails deep inside a meson build with a `cairo... not found`
  error.
  - **macOS**: `setup.sh` installs these for you via Homebrew if missing. Manually:
    `brew install cairo pkg-config pango ffmpeg`
  - **Linux**: `sudo apt install pkg-config libcairo2-dev libpango1.0-dev ffmpeg` (Ubuntu/Debian)

---

## First-time setup

Both scripts do the same thing:
1. Initialize Git LFS
2. Create a Python virtual environment at `repo/venv/`
3. Install packages from `repo/requirements.txt`
4. Print next steps

---

## After cloning an existing project repo

```bash
# Windows
setup.bat

# Linux/macOS
chmod +x setup.sh
./setup.sh
```

The script is idempotent, meaning safe to re-run if you add new packages to `requirements.txt`.

---

## Activating the venv manually

```bash
# Windows
repo\venv\Scripts\activate

# Linux/macOS
source repo/venv/bin/activate
```

Deactivate with `deactivate` when done.

---

## Adding packages

```bash
# Activate venv first, then:
pip install some-package

# Keep requirements.txt in sync:
pip freeze > requirements.txt
```

Commit `requirements.txt` changes but not the `venv/` folder (it's in `.gitignore` for this reason).

---

## Git LFS tracked file types

The following extensions are tracked via LFS (see `.gitattributes`):

| Type | Extensions |
|---|---|
| CAD / 3D | `.stl` `.step` `.f3d` `.sldprt` `.sldasm` |
| Data | `.csv` `.hdf5` `.npy` `.npz` `.pkl` |
| Media | `.mp4` `.mov` `.png` `.jpg` |

Add more with:
```bash
git lfs track "*.extension"
git add .gitattributes
```

---

## Checklist before first commit

- [ ] Rename repo folder and update `README.md` title/description
- [ ] Add link to project page on site (first line of README)
- [ ] Confirm nothing sensitive in `analysis/data/` before pushing (use `.gitignore`)
- [ ] Set license: maybe MIT for code-heavy repos, CC-BY-4.0 for docs-heavy ones