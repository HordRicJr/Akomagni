# Akomagni one-liner install (Windows)
# irm https://akomagni.dev/install/windows | iex

$ErrorActionPreference = "Stop"

$InstallDir = if ($env:AKOMAGNI_INSTALL_DIR) { $env:AKOMAGNI_INSTALL_DIR } else { "$env:LOCALAPPDATA\akomagni" }
$Repo = if ($env:AKOMAGNI_REPO) { $env:AKOMAGNI_REPO } else { "https://github.com/HordRicJr/Akomagni.git" }

Write-Host "==> Akomagni install" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3.11+ requis (python dans PATH)"
}

if (-not (Test-Path "$InstallDir\.git")) {
    git clone --depth 1 $Repo $InstallDir
} else {
    git -C $InstallDir pull --ff-only
}

python -m venv "$InstallDir\.venv"
& "$InstallDir\.venv\Scripts\pip.exe" install -U pip
& "$InstallDir\.venv\Scripts\pip.exe" install -e $InstallDir

$BinDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item "$InstallDir\.venv\Scripts\akomagni.exe" "$BinDir\akomagni.exe" -Force

Write-Host ""
Write-Host "Akomagni installé. Ajoute $BinDir au PATH si besoin."
Write-Host "  akomagni doctor"
Write-Host "  akomagni config init"
Write-Host "  akomagni run cli"
