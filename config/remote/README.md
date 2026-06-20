# Remote Access Configuration

This directory contains configuration for remote network access to Augur.

## Quick Setup

1. Install Caddy: `brew install caddy` (macOS) or see https://caddyserver.com/docs/install
2. Copy and configure user store: `cp users.yaml.example users.yaml` — edit passwords
3. Generate password hashes: `node -e "require('bcryptjs').hash('yourpassword', 10).then(console.log)"`
4. Start Caddy: `AUGUR_HOST=192.168.1.x caddy run --config config/remote/Caddyfile`
5. Trust the CA on client machines: `caddy trust` (on server), then import the CA cert on client

## Files

| File | Purpose | Git-tracked? |
|------|---------|-------------|
| `Caddyfile` | Caddy reverse proxy config | Yes |
| `users.yaml.example` | User store template | Yes |
| `users.yaml` | Actual user credentials | **No** (gitignored) |
| `.jwt-secret` | JWT signing key (auto-generated) | **No** (gitignored) |
| `README.md` | This file | Yes |

## TLS Trust (Required for Claude Desktop)

Caddy uses its internal CA for TLS certificates. Client machines need to trust this CA:

### On the Augur server (macOS)
```bash
caddy trust  # Adds Caddy's CA to macOS system keychain
```

### On Windows client
1. Find Caddy's root CA cert: `caddy trust` prints the CA location
2. Copy the CA cert file to the Windows machine
3. Double-click → Install Certificate → Local Machine → Trusted Root Certification Authorities

### Verify
```bash
curl https://192.168.1.x/api/health
```

## MCP Client Configuration

After setup, generate configs for remote clients:
```bash
python3 project-brain/capabilities/skills/platform-admin/scripts/generate_client_config.py --host 192.168.1.x
```

This generates:
- `claude_desktop_config.json` — for Claude Desktop MCP connection
- `antigravity_config.json` — for Antigravity MCP connection
