# Build FootballFloater.exe on Windows (run from repo root).
# Requires: Python 3.10+, pip install -r requirements.txt pyinstaller
#
# Optional Nuitka (often smaller/faster cold start):
#   pip install nuitka ordered-set zstandard
#   python -m nuitka --standalone --enable-plugin=tk-inter --windows-disable-console `
#     --output-dir=dist-nuitka --assume-yes-for-downloads main.py
#   Rename dist-nuitka/main.dist → FootballFloater and main.exe → FootballFloater.exe

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm football_floater.spec

$out = Join-Path "dist" "FootballFloater"
Write-Host "Built: $out\FootballFloater.exe"
Write-Host "Zip that folder for GitHub Releases."
