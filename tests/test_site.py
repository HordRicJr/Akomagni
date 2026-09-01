"""Static site structure tests for akomagni.dev."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

REQUIRED_ROUTES = ("code", "design", "write", "models", "memory")
HUB_ROUTES = ("install", "tools")


def test_site_root_exists():
    assert (SITE / "index.html").is_file()
    assert (SITE / "assets" / "style.css").is_file()


def test_site_routes_exist():
    for route in REQUIRED_ROUTES:
        page = SITE / route / "index.html"
        assert page.is_file(), f"missing route: /{route}/"


def test_site_hub_routes_exist():
    for route in HUB_ROUTES:
        page = SITE / route / "index.html"
        assert page.is_file(), f"missing hub route: /{route}/"


def test_site_pages_reference_stylesheet():
    for html in SITE.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        assert "style.css" in text, f"{html} missing stylesheet link"


def test_site_uses_relative_asset_paths():
    """GitHub project Pages serves under /Akomagni/ — absolute /assets/ paths break CSS."""
    root_index = (SITE / "index.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' in root_index
    assert 'href="/assets/style.css"' not in root_index

    for route in (*REQUIRED_ROUTES, *HUB_ROUTES):
        page = (SITE / route / "index.html").read_text(encoding="utf-8")
        assert 'href="../assets/style.css"' in page, f"{route} missing relative stylesheet"
        assert 'href="/assets/style.css"' not in page, f"{route} uses broken absolute path"


def test_install_scripts_exist_in_repo():
    """Source install scripts must exist; Pages workflow copies them to site/install/."""
    assert (ROOT / "install" / "install.sh").is_file()
    assert (ROOT / "install" / "install.ps1").is_file()


def test_pages_workflow_copies_install_scripts():
    workflow = ROOT / ".github" / "workflows" / "pages.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "site/install/linux" in text
    assert "site/install/windows" in text


def test_pages_workflow_exists():
    workflow = ROOT / ".github" / "workflows" / "pages.yml"
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")
    assert "upload-pages-artifact" in text
    assert "deploy-pages" in text
    assert "path: site" in text
