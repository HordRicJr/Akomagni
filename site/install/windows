# Akomagni one-liner install (Windows)
# irm https://hordricjr.github.io/Akomagni/install/windows | iex

$ErrorActionPreference = "Stop"

$InstallDir = if ($env:AKOMAGNI_INSTALL_DIR) { $env:AKOMAGNI_INSTALL_DIR } else { "$env:LOCALAPPDATA\akomagni" }
$Repo = if ($env:AKOMAGNI_REPO) { $env:AKOMAGNI_REPO } else { "https://github.com/HordRicJr/Akomagni.git" }
$SourceDir = $env:AKOMAGNI_SOURCE_DIR
$BinDir = if ($env:AKOMAGNI_BIN_DIR) { $env:AKOMAGNI_BIN_DIR } else { "$env:USERPROFILE\.local\bin" }
$PythonExe = "$InstallDir\.venv\Scripts\python.exe"
$AkomagniExe = "$InstallDir\.venv\Scripts\akomagni.exe"

function Invoke-Checked {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Command"
    }
}

function Test-AkomagniSource {
    param([string]$Path)
    return (Test-Path "$Path\pyproject.toml")
}

function Reset-InstallDir {
    param([string]$Path, [string]$Reason)
    if (Test-Path $Path) {
        Write-Host "==> Removing install dir ($Reason): $Path" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $Path
    }
}

Write-Host "==> Akomagni install" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ required (python in PATH). Install: winget install Python.Python.3.12"
}
Invoke-Checked { python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" }
$pyMinor = python -c "import sys; print(sys.version_info.minor)"
if ([int]$pyMinor -gt 13) {
    Write-Host "WARNING: Python 3.$pyMinor detected. Python 3.12 is recommended (winget install Python.Python.3.12)." -ForegroundColor Yellow
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git required. Install: winget install Git.Git"
}

if ($SourceDir) {
    Write-Host "==> Copying from $SourceDir"
    Reset-InstallDir -Path $InstallDir -Reason "source copy"
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force
}
elseif ((Test-Path "$InstallDir\.git") -and (Test-AkomagniSource $InstallDir)) {
    Write-Host "==> Updating existing install" -ForegroundColor Cyan
    Invoke-Checked { git -C $InstallDir pull --ff-only }
}
else {
    if (Test-Path $InstallDir) {
        Reset-InstallDir -Path $InstallDir -Reason "incomplete or broken install"
    }
    Write-Host "==> Cloning $Repo"
    Invoke-Checked { git clone --depth 1 $Repo $InstallDir }
}

if (-not (Test-AkomagniSource $InstallDir)) {
    throw "Install dir missing pyproject.toml — delete $InstallDir and retry."
}

if (-not (Test-Path "$InstallDir\.venv")) {
    Write-Host "==> Creating virtualenv"
    Invoke-Checked { python -m venv "$InstallDir\.venv" }
}

Write-Host "==> Installing Python package"
Invoke-Checked { & $PythonExe -m pip install -U pip }
Write-Host "==> Installing core dependencies"
Invoke-Checked {
    & $PythonExe -m pip install --upgrade `
        "platformdirs>=4.0" `
        "typer>=0.12" `
        "rich>=13.7" `
        "pyyaml>=6.0" `
        "psutil>=5.9" `
        "sqlite-vec>=0.1.6"
}
Write-Host "==> Installing Akomagni (editable)"
Invoke-Checked { & $PythonExe -m pip install -e $InstallDir --no-deps }

if (-not (Test-Path $AkomagniExe)) {
    throw "akomagni.exe not found after install — check pip output above."
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$DestExe = "$BinDir\akomagni.exe"
$StagingExe = "$BinDir\akomagni.exe.new"
$BackupExe = "$BinDir\akomagni.exe.old"
Copy-Item $AkomagniExe $StagingExe -Force
if (Test-Path $DestExe) {
    Remove-Item $BackupExe -Force -ErrorAction SilentlyContinue
    try {
        Move-Item -Path $DestExe -Destination $BackupExe -Force
    } catch {
        # Fallback if rename fails — last resort overwrite
        Copy-Item $StagingExe $DestExe -Force
        Remove-Item $StagingExe -Force -ErrorAction SilentlyContinue
        $StagingExe = $null
    }
}
if ($StagingExe -and (Test-Path $StagingExe)) {
    Move-Item -Path $StagingExe -Destination $DestExe -Force
}
Remove-Item $BackupExe -Force -ErrorAction SilentlyContinue

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    $updated = if ($userPath) { "$userPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    Write-Host "==> Added $BinDir to user PATH"
}
$env:Path = "$env:Path;$BinDir"

Write-Host "==> Smoke test"
$env:PYTHONUTF8 = "1"
Invoke-Checked { & "$BinDir\akomagni.exe" --version }
Invoke-Checked { & "$BinDir\akomagni.exe" doctor --json *> $null }

Write-Host ""
Write-Host "Akomagni installed successfully." -ForegroundColor Green
Write-Host "  akomagni doctor"
Write-Host "  akomagni config init"
Write-Host "  akomagni config extras inference"
Write-Host "  akomagni update"
Write-Host "  akomagni run cli"
