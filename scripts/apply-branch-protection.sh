#!/usr/bin/env bash
# Apply branch protection rules for develop and main (requires repo admin + gh CLI).
# Usage: ./scripts/apply-branch-protection.sh [owner/repo]
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

REQUIRED_CHECKS='[
  {"context": "Lint & format (Ruff)"},
  {"context": "Documentation i18n parity"},
  {"context": "Coverage (≥90%)"},
  {"context": "Install script smoke (linux)"},
  {"context": "Dependency audit (pip-audit)"},
  {"context": "Static analysis (Bandit)"},
  {"context": "Secret scanning (Gitleaks)"}
]'

apply_protection() {
  local branch="$1"
  local reviews="$2"
  echo "Applying protection to ${REPO}@${branch} (reviews=${reviews})..."
  gh api \
    --method PUT \
    "repos/${REPO}/branches/${branch}/protection" \
    --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "checks": ${REQUIRED_CHECKS}
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": ${reviews},
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
}

apply_protection develop 0
apply_protection main 1
echo "Done. Verify in GitHub → Settings → Branches."
