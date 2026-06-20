# Mode: Default (no flags)

Interactive step-by-step setup for new users and new-project onboarding.

## Quick Start for New Users

**Prerequisites:** Python >=3.11, Node.js >=22, Git installed. Recommended: ripgrep (`rg`) for fast full-text search (`winget install BurntSushi.ripgrep.MSVC` / `brew install ripgrep` / `apt install ripgrep`).

> On Windows, prefer the native installer and guide in `docs/guides/installation-windows.md`. The shell snippets below assume a Unix-like terminal unless stated otherwise.

### Step 1: Clone Repository

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone https://github.com/augur-os/augur-os.git Augur
cd Augur
```

### Step 2: Configure Git Hooks

```bash
git config core.hooksPath .githooks
```

This activates guards that block binary files, large files (>200KB), and commits to forbidden paths.

### Step 3: Install Dependencies

```bash
# Enable pnpm via corepack (built into Node.js)
corepack enable

# Install Node.js dependencies (uses pnpm global store)
pnpm install

# Install Python dependencies (uses uv global cache)
uv sync
```

### Step 3b: Optional on macOS/Linux: Set Up direnv (auto-activate venv)

direnv auto-activates the Python virtual environment when you `cd` into the project. Without it, bare `python` uses the system Python which lacks project dependencies.

```bash
# Install direnv (macOS)
brew install direnv

# Add shell hook (zsh — for bash, replace zsh with bash)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# Allow the project .envrc
direnv allow
```

After this, `python` and `pip` will always resolve to the project venv inside this repo.

Windows users can skip direnv and activate the repo venv directly with `.\.venv\Scripts\Activate.ps1` when they need an interactive shell inside the project.

### Step 4: Configure IDE

MCP is configured from the repo root with the canonical script. First list the supported IDEs, then auto-configure the one you want:

```bash
python scripts/configure_mcp.py --list-ides
python scripts/configure_mcp.py --client cursor --auto
```

### Step 5: Start Dashboard

Use the managed dev workflow from an Augur AI-client session, for example `/dev-build`.

Open **http://localhost:3000** after the workflow reports the dashboard is active.

### Step 6: Verify Setup

1. Open Claude Desktop - Augur MCP should appear in tools
2. Open Dashboard - should load without errors
3. Open a new Augur session in the repo root so the repository instructions and key docs load as the canonical context source

---

## Full Onboarding (Existing Projects)

For adding a new project to an existing Augur installation.

### 1. Gather Project Information

| Field | Description | Example |
|-------|-------------|---------|
| Project name | Short identifier | `my-saas-app` |
| Project type | Category | `webapp`, `api`, `library`, `cli` |
| Repository URL | Git remote | `github.com/user/repo` |
| Tech stack | Primary technologies | `Next.js, Python, PostgreSQL` |

### 2. Initialize Configuration

```bash
python project-brain/capabilities/skills/onboard/scripts/augur_init.py "PROJECT_NAME" --repo "REPOSITORY_URL"
```

### 3. Configure Skills

| Project Type | Recommended Skills |
|--------------|-------------------|
| webapp | frontend, validator, developer |
| api | developer, security, validator |
| library | developer, knowledge, oss-manager |
| data | data-engineer, data-scientist |

### 4. Set Autonomy Level

| Level | Behavior |
|-------|----------|
| 0.0-0.3 | Manual approval for all changes |
| 0.4-0.6 | Auto-execute reads, manual for writes |
| 0.7-0.8 | Auto-execute most, manual for destructive |
| 0.9-1.0 | Full automation |

Update via dashboard Settings > General.

---

## Post-Onboarding Checklist

- [ ] Repository cloned
- [ ] Git hooks configured (`git config core.hooksPath .githooks`)
- [ ] Dependencies installed (pnpm + uv)
- [ ] direnv installed and `.envrc` allowed on macOS/Linux, or Windows venv activation verified with `.\.venv\Scripts\Activate.ps1`
- [ ] IDE integration configured (Claude Desktop/Claude Code CLI/Cursor)
- [ ] Dashboard running at localhost:3000
- [ ] MCP tools visible in IDE (`claude mcp list` for Claude Code CLI)
- [ ] If the user wants to create or extend a skill, hand off to `/evolve`
