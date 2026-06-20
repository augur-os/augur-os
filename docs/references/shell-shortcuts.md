# Shell Shortcuts for Multi-Project Augur

Add to your `.zshrc` or `.bashrc` for project-aware navigation.

## Project-aware helpers

```bash
PROJECTS_DIR="$HOME/Projects"

augur-cd() {
  local project="${1:-Augur}"
  cd "$PROJECTS_DIR/$project"
}

augur-dev() {
  local project="${1:-Augur}"
  cd "$PROJECTS_DIR/$project/apps/dashboard"
  local port=$(grep 'port:' "$PROJECTS_DIR/$project/project.yaml" | awk '{print $2}')
  npm run dev -- --port "${port:-3000}"
}

augur-daemon() {
  local project="${1:-Augur}"
  local action="${2:-status}"
  cd "$PROJECTS_DIR/$project"
  python project-brain/capabilities/skills/daemon/scripts/unified_daemon.py "$action"
}

augur-rebuild() {
  local project="${1:-Augur}"
  local port=$(grep 'port:' "$PROJECTS_DIR/$project/project.yaml" | awk '{print $2}')
  cd "$PROJECTS_DIR/$project"
  python project-brain/capabilities/skills/daemon/scripts/cleanup_processes.py --port "${port:-3000}" --force
  cd apps/dashboard && npm run build:safe
}
```

## Usage

```bash
augur-dev              # Start Project0 (Augur) dashboard
augur-dev myapp        # Start myapp dashboard on its configured port
augur-daemon myapp     # Check myapp daemon status
augur-daemon myapp start  # Start myapp daemon
```
