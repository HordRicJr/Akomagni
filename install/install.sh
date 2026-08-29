#!/usr/bin/env bash
set -euo pipefail

# Akomagni one-liner install (Linux / macOS)
# curl -fsSL https://akomagni.dev/install/linux | bash

AKOMAGNI_REPO="${AKOMAGNI_REPO:-https://github.com/HordRicJr/Akomagni.git}"
INSTALL_DIR="${AKOMAGNI_INSTALL_DIR:-$HOME/.local/share/akomagni}"

echo "==> Akomagni install"
command -v python3 >/dev/null || { echo "Python 3.11+ requis"; exit 1; }
command -v git >/dev/null || { echo "git requis"; exit 1; }

mkdir -p "$(dirname "$INSTALL_DIR")"
if [ ! -d "$INSTALL_DIR/.git" ]; then
  git clone --depth 1 "$AKOMAGNI_REPO" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull --ff-only
fi

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install -U pip
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/.venv/bin/akomagni" "$BIN_DIR/akomagni"

echo ""
echo "Akomagni installé. Ajoute ~/.local/bin au PATH si besoin."
echo "  akomagni doctor"
echo "  akomagni config init"
echo "  akomagni run cli"
