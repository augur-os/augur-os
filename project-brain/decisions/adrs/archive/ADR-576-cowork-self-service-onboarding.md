---
status: Implemented
date: 2026-03-31
deciders:
  - Gur Sannikov
related:
  - ADR-437
  - ADR-503
hub: null
tags:
  - onboarding
  - install
  - cowork
  - claude-desktop
  - mcp
superseded_by: null
---

# ADR-576: Cowork Self-Service Onboarding

## Context

Installing Augur into Cowork (Claude Desktop) previously required someone to run `plugin_assembler.py --target cowork --install` from inside a working Augur checkout. There was no self-service path for a user arriving from the web. The existing `install.sh` already supported Claude Code, Codex, Cursor, and other clients via `--from <client>`, but `cowork` was not a recognized platform target — `configure_mcp.py` reported "unknown client", and no plugin assembly step ran.

A new user finding Augur online should be able to install it into Cowork with a single terminal command, the same way they can today for other clients.

## Decision

Extend the three existing install files — `install.sh`, `configure_mcp.py`, and `skills/onboard/install.md` — to recognize `cowork` as a platform target. Map it to `claude_desktop` for MCP wiring, run the plugin assembler for Cowork packaging, and show Cowork-specific post-install messaging.

### Entry point

```
curl -fsSL https://install.augur.run | bash -s -- --from cowork
```

### `scripts/configure_mcp.py`

Add an alias mapping after client_key normalization so that `--client cowork` resolves to `claude_desktop`:

```python
_PLATFORM_ALIASES = {"cowork": "claude_desktop"}
client_key = _PLATFORM_ALIASES.get(client_key, client_key)
```

### `scripts/install.sh`

Three changes:

1. Map `cowork` to `claude_desktop` before the `configure_mcp.py --client` call (belt-and-suspenders with the alias inside `configure_mcp.py`).
2. After the existing codex plugin block, add a Cowork plugin assembly block that runs `skills/plugin-pack/scripts/plugin_assembler.py --target cowork --install` when `INSTALL_FROM=cowork` (or `cowork` is in `CONFIGURE_CLIENTS`).
3. Replace the generic "Next steps" message with a platform-aware variant: when `INSTALL_FROM=cowork`, show "Restart Claude Desktop / Augur tools and skills will appear automatically / Try /ask, /search, /save"; otherwise keep the generic dev message.

### `skills/onboard/install.md` (and the synced `dist/skills-pack/install.md`)

- Add a row to the platform detection table: `| You are Claude Desktop (Cowork) | cowork |`.
- After Step 1 (platform detection), add routing: if `PLATFORM` is `cowork`, skip Step 2 (welcome choice) and go directly to Step 4 (Full System Install). Cowork requires the MCP server, so the skills-pack option does not apply.

### What the user experiences

1. Visit augur.run, copy one-liner.
2. Terminal: prerequisites check, repo clone, deps install (~3 min).
3. MCP server wired into `claude_desktop_config.json`.
4. Cowork plugin assembled and installed to `local-desktop-app-uploads`.
5. Terminal shows: "Restart Claude Desktop".
6. After restart, Augur skills, commands, and MCP tools appear in Claude Desktop.

## Consequences

### Positive
- Cowork onboarding becomes a single-command flow, parity with other clients.
- The platform alias is enforced in two places (install.sh and configure_mcp.py) so direct `--client cowork` calls also work.
- Post-install messaging matches user expectations on each platform.

### Negative
- Public marketplace listing is out of scope and still requires a separate Anthropic submission.
- A Cowork-only lightweight install (no Node, no dashboard) is not yet available.
- Windows is unsupported because Claude Desktop paths in the IDE registry are macOS-only.

### Neutral
- The dist skills-pack copy of `install.md` must be kept in sync manually.

## Alternatives Considered

### Alternative 1: Document a manual `plugin_assembler.py` invocation as the install path
Rejected because users arriving from the web cannot reasonably be expected to clone the repo and run the assembler by hand.

### Alternative 2: Build a separate `cowork-install.sh` script
Rejected. The existing `install.sh` already handles every other client; adding a parallel script would diverge maintenance and duplicate the prerequisites/dependencies logic.

## References
- Plan: docs/superpowers/plans/2026-03-31-cowork-self-service-onboarding.md
- Spec: docs/superpowers/specs/2026-03-31-cowork-self-service-onboarding-design.md
