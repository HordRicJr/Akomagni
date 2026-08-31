# Outils MCP agent

Outils sandboxés (fichiers, shell, git) pour le mode agent via MCP.

## Outils

| Outil | Description | Approbation |
|-------|-------------|-------------|
| `fs_read` | Lire un fichier UTF-8 | Non |
| `fs_write` | Écrire un fichier (écrasement = approbation) | À l'écrasement |
| `fs_list` | Lister un répertoire | Non |
| `fs_delete` | Supprimer fichier ou dossier vide | Oui |
| `shell_run` | Commande shell dans le workspace | Motifs destructifs |
| `git_status` | `git status` | Non |
| `git_diff` | `git diff` | Non |
| `git_log` | Commits récents | Non |
| `git_push` | Push vers remote | Oui |

Les commandes destructives (`rm -rf`, `git push`, `git reset --hard`, etc.) sont mises en file d'attente.

## CLI

```bash
akomagni mcp serve
akomagni mcp pending
akomagni mcp approve <request-id>
akomagni mcp reject <request-id>
```

## Configuration Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "akomagni": {
      "command": "akomagni",
      "args": ["mcp", "serve", "--workspace", "/chemin/vers/projet"]
    }
  }
}
```

## Configuration (`~/.akomagni/config.yaml`)

```yaml
mcp:
  workspace: null
  auto_approve: false
  shell_timeout: 30
```
