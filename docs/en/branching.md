## Branching strategy

Akomagni uses a **Git Flow** inspired workflow:

```
main          ← stable releases only (tagged versions)
  ↑
develop       ← integration branch (default target for PRs)
  ↑
feature/#123-short-description   ← your work branch
```

### Rules

| Branch | Purpose | Who merges |
|--------|---------|------------|
| `main` | Production-ready releases | Maintainers only, from `develop` when stable |
| `develop` | Daily integration | Via reviewed PRs |
| `feature/*`, `fix/*`, `chore/*` | Individual changes | Contributor → PR to `develop` |

### Workflow for contributors

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
git checkout develop
git pull origin develop
git checkout -b feature/42-llama-server

# … work, commit …

git push -u origin feature/42-llama-server
# Open PR → base: develop (NOT main)
```

### Commit messages (linked to issues)

Reference the GitHub issue in every commit:

```
feat(#42): integrate llama-server subprocess
fix(#15): correct VRAM detection on Windows
docs(#8): add French getting-started section
test(#21): raise coverage for flow orchestrator
chore(#30): update CI security workflow
```

Format: `<type>(#<issue>): <imperative summary>`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `security`.

### Release path

1. Features merge into `develop` via PR
2. CI must pass (quality, tests, 90% coverage, security, secrets)
3. When `develop` is stable → PR `develop` → `main`
4. Tag release on `main` (`v0.2.0`)

### Branch protection (maintainers)

CI workflows: **Quality**, **Test**, **Security** (see `.github/workflows/`). Dependabot opens weekly update PRs (`.github/dependabot.yml`).

To enforce rules on GitHub (requires admin):

```bash
# Linux / macOS
bash scripts/apply-branch-protection.sh

# Windows (PowerShell)
.\scripts\apply-branch-protection.ps1
```

| Branch | Reviews required | Status checks |
|--------|----------------|---------------|
| `develop` | 0 (solo maintainer OK) | Quality + Test + Security |
| `main` | 1 approval | Same checks, no direct push |

### GitHub Pages (maintainers)

The static site lives in `site/` and deploys via `.github/workflows/pages.yml` on push to `main`.

Pages must be enabled once (admin):

```bash
bash scripts/enable-github-pages.sh
# Windows:
.\scripts\enable-github-pages.ps1
```

The script allows deployment from **`main`** and **`develop`** (`github-pages` environment). Without `main`, deploy fails after merging to `main`.

Then merge `develop` → `main` (or re-run the Pages workflow). Optional custom domain: `akomagni.dev` in repo Settings → Pages.

See [ROADMAP.md](ROADMAP.md) and [GitHub Issues](https://github.com/HordRicJr/Akomagni/issues) for planned work.
