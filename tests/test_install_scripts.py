"""Tests for install scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

INSTALL_DIR = Path(__file__).resolve().parents[1] / "install"


def test_install_sh_contains_path_and_smoke():
    text = (INSTALL_DIR / "install.sh").read_text(encoding="utf-8")
    assert "Smoke test" in text
    assert "doctor --json" in text
    assert "AKOMAGNI_SOURCE_DIR" in text
    assert "AKOMAGNI_BRANCH" in text
    assert '--branch "$AKOMAGNI_BRANCH"' in text or '--branch "$AKOMAGNI_BRANCH"' in text
    assert "python3 -c" in text


def test_install_ps1_contains_path_and_smoke():
    text = (INSTALL_DIR / "install.ps1").read_text(encoding="utf-8")
    assert "Smoke test" in text
    assert "SetEnvironmentVariable" in text
    assert "AKOMAGNI_SOURCE_DIR" in text
    assert "AKOMAGNI_BRANCH" in text
    assert "origin/$Branch" in text or "origin/$Branch" in text
    assert "--branch $Branch" in text


@pytest.mark.skipif(sys.platform == "win32", reason="bash install smoke is Unix-only")
def test_install_sh_local_smoke(tmp_path):
    install_target = tmp_path / "akomagni-app"
    bin_dir = tmp_path / "bin"
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "AKOMAGNI_INSTALL_DIR": str(install_target),
            "AKOMAGNI_SOURCE_DIR": str(repo_root),
            "AKOMAGNI_BIN_DIR": str(bin_dir),
            "HOME": str(tmp_path / "home"),
        }
    )
    (tmp_path / "home").mkdir()
    subprocess.run(
        ["bash", str(INSTALL_DIR / "install.sh")],
        check=True,
        env=env,
        cwd=repo_root,
    )
    akomagni = bin_dir / "akomagni"
    assert akomagni.is_file() or akomagni.is_symlink()
    result = subprocess.run(
        [str(akomagni), "--version"],
        check=True,
        capture_output=True,
        text=True,
        env={**env, "PATH": f"{bin_dir}:{env.get('PATH', '')}"},
    )
    assert "akomagni" in result.stdout
