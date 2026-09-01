#!/usr/bin/env bash
set -euo pipefail

# Akomagni one-liner install (Linux / macOS)
# curl -fsSL https://akomagni.dev/install/linux | bash

AKOMAGNI_REPO="${AKOMAGNI_REPO:-https://github.com/HordRicJr/Akomagni.git}"
INSTALL_DIR="${AKOMAGNI_INSTALL_DIR:-$HOME/.local/share/akomagni}"
BIN_DIR="${AKOMAGNI_BIN_DIR:-$HOME/.local/bin}"
AKOMAGNI_SOURCE_DIR="${AKOMAGNI_SOURCE_DIR:-}"

echo "==> Akomagni install"

command -v python3 >/dev/null || { echo "Python 3.11+ required"; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ required"; exit 1; }
command -v git >/dev/null || { echo "git required"; exit 1; }

mkdir -p "$(dirname "$INSTALL_DIR")"
if [ -n "$AKOMAGNI_SOURCE_DIR" ]; then
  echo "==> Copying from $AKOMAGNI_SOURCE_DIR"
  mkdir -p "$INSTALL_DIR"
  cp -a "$AKOMAGNI_SOURCE_DIR/." "$INSTALL_DIR/"
  rm -rf "$INSTALL_DIR/.venv"
elif [ -d "$INSTALL_DIR/.git" ]; then
  echo "==> Updating existing install"
  git -C "$INSTALL_DIR" pull --ff-only
else
  if [ -d "$INSTALL_DIR" ]; then
    echo "==> Removing incomplete install at $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
  fi
  git clone --depth 1 "$AKOMAGNI_REPO" "$INSTALL_DIR"
fi

if [ ! -d "$INSTALL_DIR/.venv" ]; then
  python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install -U pip
echo "==> Installing core dependencies"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade \
  "platformdirs>=4.0" \
  "typer>=0.12" \
  "rich>=13.7" \
  "pyyaml>=6.0" \
  "psutil>=5.9" \
  "sqlite-vec>=0.1.6"
echo "==> Installing Akomagni (editable)"
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR" --no-deps

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/.venv/bin/akomagni" "$BIN_DIR/akomagni"

path_line='export PATH="'"$BIN_DIR"':$PATH"'
for rc in "$HOME/.bashrc" "$HOME/.zprofile" "$HOME/.zshrc"; do
  if [ -f "$rc" ] && ! grep -qF "$BIN_DIR" "$rc"; then
    {
      echo ""
      echo "# Akomagni"
      echo "$path_line"
    } >>"$rc"
    echo "==> Added $BIN_DIR to $rc"
  fi
done

export PATH="$BIN_DIR:$PATH"
echo "==> Smoke test"
"$BIN_DIR/akomagni" --version
"$BIN_DIR/akomagni" doctor --json >/dev/null

echo ""
echo "Akomagni installed."
echo "  akomagni doctor"
echo "  akomagni config init"
echo "  akomagni run cli"
