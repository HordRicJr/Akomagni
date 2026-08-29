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

See [ROADMAP.md](ROADMAP.md) and [GitHub Issues](https://github.com/HordRicJr/Akomagni/issues) for planned work.
