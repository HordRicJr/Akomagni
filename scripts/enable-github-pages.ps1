# Enable GitHub Pages with GitHub Actions deployment (requires repo admin + gh CLI).
# Usage: .\scripts\enable-github-pages.ps1 [-Repo owner/name]

param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = gh repo view --json nameWithOwner -q .nameWithOwner
}

$envName = "github-pages"

Write-Host "Enabling GitHub Pages (workflow build) on ${Repo}..."
try {
    gh api --method POST "repos/$Repo/pages" -f build_type=workflow | Out-Null
} catch {
    Write-Host "  Pages already enabled (continuing)"
}

Write-Host "Allowing deploy from main and develop on ${envName}..."
foreach ($branch in @("main", "develop")) {
    $existing = gh api "repos/$Repo/environments/$envName/deployment-branch-policies" `
        --jq ".branch_policies[].name" 2>$null
    if ($existing -contains $branch) {
        Write-Host "  ${branch}: already allowed"
    } else {
        gh api --method POST "repos/$Repo/environments/$envName/deployment-branch-policies" `
            -f "name=$branch" | Out-Null
        Write-Host "  ${branch}: added"
    }
}

Write-Host "Done. Verify: https://github.com/$Repo/settings/pages"
