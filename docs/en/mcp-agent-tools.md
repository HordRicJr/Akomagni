# MCP agent tools

Sandboxed filesystem, shell, and git tools for agent mode via MCP.

## Tools

| Tool | Description | Approval |
|------|-------------|----------|
| `fs_read` | Read a UTF-8 file | No |
| `fs_write` | Write a file (overwrite needs approval) | On overwrite |
| `fs_list` | List directory entries | No |
| `fs_delete` | Delete file or empty directory | Yes |
| `shell_run` | Run shell command in workspace | Destructive patterns |
| `git_status` | `git status` | No |
| `git_diff` | `git diff` | No |
| `git_log` | Recent commits | No |
| `git_push` | Push to remote | Yes |

Destructive shell patterns include `rm -rf`, `git push`, `git reset --hard`, etc.

## CLI

```bash
# Start MCP stdio server (requires pip install 'akomagni[agent]')
akomagni mcp serve

# Review / approve / reject queued operations
akomagni mcp pending
akomagni mcp approve <request-id>
akomagni mcp reject <request-id>
```

## Cursor / Claude Desktop config

```json
{
  "mcpServers": {
    "akomagni": {
      "command": "akomagni",
      "args": ["mcp", "serve", "--workspace", "/path/to/project"]
    }
  }
}
```

## Configuration (`~/.akomagni/config.yaml`)

```yaml
mcp:
  workspace: null        # default: BMAD project root or cwd
  auto_approve: false    # never enable on shared machines
  shell_timeout: 30
```
