#!/usr/bin/env bash
# Enable GitHub Pages with GitHub Actions deployment (requires repo admin + gh CLI).
# Usage: ./scripts/enable-github-pages.sh [owner/repo]
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

echo "Enabling GitHub Pages (workflow build) on ${REPO}..."
gh api \
  --method POST \
  "repos/${REPO}/pages" \
  -f build_type=workflow

echo "Done. Verify: https://github.com/${REPO}/settings/pages"
echo "After merge to main, re-run the Pages workflow or push a site/ change."
