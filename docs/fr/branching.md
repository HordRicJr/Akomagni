## Stratégie de branches

Akomagni utilise un workflow inspiré de **Git Flow** :

```
main          ← releases stables uniquement
  ↑
develop       ← branche d'intégration (cible des PR)
  ↑
feature/#123-description-courte
```

### Règles

| Branche | Rôle | Fusion |
|---------|------|--------|
| `main` | Production stable | Mainteneurs, depuis `develop` quand stable |
| `develop` | Intégration quotidienne | Via PR reviewées |
| `feature/*`, `fix/*`, `chore/*` | Travail individuel | Contributeur → PR vers `develop` |

### Workflow contributeur

```bash
git checkout develop
git pull origin develop
git checkout -b feature/42-llama-server
# … travail, commits …
git push -u origin feature/42-llama-server
# Ouvrir PR → base : develop (PAS main)
```

### Messages de commit (liés aux issues)

```
feat(#42): intégrer llama-server
fix(#15): correction détection VRAM Windows
docs(#8): guide démarrage en français
```

Format : `<type>(#<issue>): <résumé>`

### Release

1. Features → `develop` via PR
2. CI verte (qualité, tests, couverture 90 %, sécurité, secrets)
3. `develop` stable → PR vers `main`
4. Tag `v0.2.0` sur `main`

### Protection des branches (mainteneurs)

Workflows CI : **Quality**, **Test**, **Security** (voir `.github/workflows/`). Dependabot ouvre des PR hebdomadaires (`.github/dependabot.yml`).

Pour appliquer les règles sur GitHub (droits admin requis) :

```bash
bash scripts/apply-branch-protection.sh
# ou sous Windows :
.\scripts\apply-branch-protection.ps1
```

| Branche | Reviews | Checks |
|---------|---------|--------|
| `develop` | 0 | Quality + Test + Security |
| `main` | 1 | Idem, pas de push direct |

### GitHub Pages (mainteneurs)

Site statique dans `site/`, déployé via `.github/workflows/pages.yml` sur push vers `main`.

Activer Pages une fois (admin) :

```bash
bash scripts/enable-github-pages.sh
# ou :
.\scripts\enable-github-pages.ps1
```

Le script autorise le déploiement depuis **`main`** et **`develop`** (environnement `github-pages`). Sans `main`, le deploy échoue après merge vers `main`.

Puis merge `develop` → `main` (ou relancer le workflow Pages). Domaine custom optionnel : `akomagni.dev` dans Settings → Pages.

Voir [ROADMAP.md](../../ROADMAP.md) et les [Issues GitHub](https://github.com/HordRicJr/Akomagni/issues).
