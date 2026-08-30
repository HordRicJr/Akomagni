# Akomagni one-liner install (Windows)
# irm https://akomagni.dev/install/windows | iex

$ErrorActionPreference = "Stop"

$InstallDir = if ($env:AKOMAGNI_INSTALL_DIR) { $env:AKOMAGNI_INSTALL_DIR } else { "$env:LOCALAPPDATA\akomagni" }
$Repo = if ($env:AKOMAGNI_REPO) { $env:AKOMAGNI_REPO } else { "https://github.com/HordRicJr/Akomagni.git" }
$SourceDir = $env:AKOMAGNI_SOURCE_DIR
$BinDir = if ($env:AKOMAGNI_BIN_DIR) { $env:AKOMAGNI_BIN_DIR } else { "$env:USERPROFILE\.local\bin" }

Write-Host "==> Akomagni install" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ required (python in PATH)"
}
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11+ required"
}

if ($SourceDir) {
    Write-Host "==> Copying from $SourceDir"
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force
    if (Test-Path "$InstallDir\.venv") {
        Remove-Item -Recurse -Force "$InstallDir\.venv"
    }
}
elseif (-not (Test-Path "$InstallDir\.git")) {
    git clone --depth 1 $Repo $InstallDir
}
else {
    git -C $InstallDir pull --ff-only
}

if (-not (Test-Path "$InstallDir\.venv")) {
    python -m venv "$InstallDir\.venv"
}
& "$InstallDir\.venv\Scripts\pip.exe" install -U pip
& "$InstallDir\.venv\Scripts\pip.exe" install -e $InstallDir

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item "$InstallDir\.venv\Scripts\akomagni.exe" "$BinDir\akomagni.exe" -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    $updated = if ($userPath) { "$userPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    Write-Host "==> Added $BinDir to user PATH"
}
$env:Path = "$env:Path;$BinDir"

Write-Host "==> Smoke test"
& "$BinDir\akomagni.exe" --version
& "$BinDir\akomagni.exe" doctor --json | Out-Null

Write-Host ""
Write-Host "Akomagni installed."
Write-Host "  akomagni doctor"
Write-Host "  akomagni config init"
Write-Host "  akomagni run cli"
