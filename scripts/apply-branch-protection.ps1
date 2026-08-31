# Apply branch protection rules for develop and main (requires repo admin + gh CLI).
# Usage: .\scripts\apply-branch-protection.ps1 [-Repo owner/name]

param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = gh repo view --json nameWithOwner -q .nameWithOwner
}

$requiredChecks = @(
    @{ context = "Lint & format (Ruff)" },
    @{ context = "Documentation i18n parity" },
    @{ context = "Coverage (≥90%)" },
    @{ context = "Install script smoke (linux)" },
    @{ context = "Dependency audit (pip-audit)" },
    @{ context = "Static analysis (Bandit)" },
    @{ context = "Secret scanning (Gitleaks)" }
)

function Apply-Protection {
    param(
        [string]$Branch,
        [int]$ReviewCount
    )
    Write-Host "Applying protection to ${Repo}@${Branch} (reviews=${ReviewCount})..."
    $body = @{
        required_status_checks = @{
            strict = $true
            checks = $requiredChecks
        }
        enforce_admins = $false
        required_pull_request_reviews = @{
            required_approving_review_count = $ReviewCount
            dismiss_stale_reviews = $true
        }
        restrictions = $null
        required_linear_history = $false
        allow_force_pushes = $false
        allow_deletions = $false
    } | ConvertTo-Json -Depth 6 -Compress

    $body | gh api --method PUT "repos/$Repo/branches/$Branch/protection" --input -
}

Apply-Protection -Branch develop -ReviewCount 0
Apply-Protection -Branch main -ReviewCount 1
Write-Host "Done. Verify in GitHub → Settings → Branches."
