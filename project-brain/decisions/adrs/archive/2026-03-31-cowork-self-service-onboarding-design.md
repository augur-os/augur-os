# Cowork Self-Service Onboarding

**Date:** 2026-03-31
**Status:** Approved
**Goal:** Let a new user who finds Augur online install it into Claude Desktop (Cowork) with a single terminal command.

## Problem

Today, installing Augur into Cowork requires someone to run `plugin_assembler.py --target cowork --install` from inside a working Augur checkout. There is no self-service path for a user arriving from the web. The existing `install.sh` handles Claude Code, Codex, Cursor, etc., but not Cowork.

## Solution

Extend the existing install infrastructure with a `cowork` platform target. One entry point, one script:

```
curl -fsSL https://install.augur.run | bash -s -- --from cowork
```

This runs the full system install (Python, Node, repo clone, deps) and adds two Cowork-specific steps at the end:
1. Wire the MCP server into `claude_desktop_config.json`
2. Assemble and install the Cowork plugin (skills + commands + manifest)

## Changes

### 1. `scripts/install.sh`

**a) Platform alias for MCP config**

Before the `configure_mcp.py --client` call, map `cowork` to `claude_desktop`:

```bash
MCP_CLIENT="$INSTALL_FROM"
if [ "$INSTALL_FROM" = "cowork" ]; then
    MCP_CLIENT="claude_desktop"
fi
```

Use `$MCP_CLIENT` instead of `$INSTALL_FROM` in the `configure_mcp.py --client` call.

**b) Cowork plugin assembly**

After the existing codex plugin block (line ~464), add a parallel block:

```bash
if [[ "$INSTALL_FROM" == "cowork" ]] || [[ "$CONFIGURE_CLIENTS" == *"cowork"* ]]; then
    ASSEMBLER="${INSTALL_DIR}/skills/plugin-pack/scripts/plugin_assembler.py"
    if [ -f "$ASSEMBLER" ]; then
        print_step "Assembling Cowork plugin..."
        PYTHONPATH="${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/skills/plugin-pack/scripts" \
            uv run python "$ASSEMBLER" --target cowork --install \
            || print_warning "Cowork plugin assembly skipped"
    fi
fi
```

**c) Platform-aware "Next steps" message**

Replace the generic closing message with a conditional:

```bash
if [ "$INSTALL_FROM" = "cowork" ]; then
    echo "Next steps:"
    echo "  1) Restart Claude Desktop"
    echo "  2) Augur tools and skills will appear automatically"
    echo "  3) Try: /ask, /search, or /save"
else
    # existing generic message
fi
```

### 2. `skills/onboard/install.md`

**a) Add cowork to platform detection table**

```
| You are Claude Desktop (Cowork) | cowork |
```

**b) Route cowork directly to full install**

After Step 1 (platform detection), add:

```
If PLATFORM is `cowork`, skip Step 2 (welcome choice) and go directly to Step 4 (Full System).
The skills-pack option doesn't apply — Cowork needs the MCP server for tools to work.
```

### 3. `scripts/configure_mcp.py`

Add `cowork` as an alias for `claude_desktop` in the client matching logic (line 201, inside the `if args.client:` block):

```python
# Normalize platform aliases
PLATFORM_ALIASES = {"cowork": "claude_desktop"}
client_key = PLATFORM_ALIASES.get(client_key, client_key)
```

## What the user experiences

1. User visits augur.run, copies the one-liner
2. Terminal: prerequisites check, repo clone, deps install (~3 min)
3. MCP server wired into Claude Desktop config
4. Cowork plugin assembled and installed to `local-desktop-app-uploads`
5. Terminal shows: "Restart Claude Desktop"
6. User restarts Claude Desktop — sees 41 skills, 3 commands, full MCP tool access

## Files modified

| File | Change |
|------|--------|
| `scripts/install.sh` | Platform alias, plugin assembly block, custom messaging |
| `skills/onboard/install.md` | Add cowork platform, route to full install |
| `scripts/configure_mcp.py` | Add cowork alias mapping |

## Not in scope

- Public marketplace listing (requires Anthropic marketplace submission, separate effort)
- Cowork-only lightweight install without Node/dashboard (could be a future option)
- Windows support for Cowork (Claude Desktop paths are macOS-only in current IDE registry)
