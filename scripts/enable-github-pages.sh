#!/usr/bin/env bash
# Enable GitHub Pages with GitHub Actions deployment (requires repo admin + gh CLI).
# Usage: ./scripts/enable-github-pages.sh [owner/repo]
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
ENV="github-pages"

echo "Enabling GitHub Pages (workflow build) on ${REPO}..."
gh api \
  --method POST \
  "repos/${REPO}/pages" \
  -f build_type=workflow 2>/dev/null || true

echo "Allowing deploy from main and develop on ${ENV}..."
for branch in main develop; do
  if gh api "repos/${REPO}/environments/${ENV}/deployment-branch-policies" \
    --jq ".branch_policies[].name" 2>/dev/null | grep -qx "${branch}"; then
    echo "  ${branch}: already allowed"
  else
    gh api \
      --method POST \
      "repos/${REPO}/environments/${ENV}/deployment-branch-policies" \
      -f "name=${branch}"
    echo "  ${branch}: added"
  fi
done

echo "Done. Verify: https://github.com/${REPO}/settings/pages"
