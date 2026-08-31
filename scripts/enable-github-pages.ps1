# Enable GitHub Pages with GitHub Actions deployment (requires repo admin + gh CLI).
# Usage: .\scripts\enable-github-pages.ps1 [-Repo owner/name]

param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = gh repo view --json nameWithOwner -q .nameWithOwner
}

Write-Host "Enabling GitHub Pages (workflow build) on ${Repo}..."
gh api --method POST "repos/$Repo/pages" -f build_type=workflow
Write-Host "Done. Verify: https://github.com/$Repo/settings/pages"
Write-Host "After merge to main, re-run the Pages workflow or push a site/ change."
