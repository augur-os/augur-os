# Cowork Self-Service Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a new user install Augur into Claude Desktop (Cowork) with `curl ... | bash -s -- --from cowork`.

**Architecture:** Extend the three existing install files — `install.sh`, `configure_mcp.py`, and `install.md` — to recognize `cowork` as a platform target. Map it to `claude_desktop` for MCP wiring, run the plugin assembler for Cowork packaging, and show Cowork-specific post-install messaging.

**Tech Stack:** Bash (install.sh), Python (configure_mcp.py), Markdown (install.md)

---

### Task 1: Add `cowork` alias to `configure_mcp.py`

**Files:**
- Modify: `scripts/configure_mcp.py:201-202`

- [ ] **Step 1: Add alias mapping after client_key normalization**

In `scripts/configure_mcp.py`, after line 202 (`client_key = args.client.strip().replace("-", "_").lower()`), add the alias resolution:

```python
        client_key = args.client.strip().replace("-", "_").lower()
        # Normalize platform aliases (cowork -> claude_desktop)
        _PLATFORM_ALIASES = {"cowork": "claude_desktop"}
        client_key = _PLATFORM_ALIASES.get(client_key, client_key)
```

- [ ] **Step 2: Verify the alias resolves**

Run:
```bash
uv run python scripts/configure_mcp.py --client cowork --check --verbose
```

Expected: output mentions "Claude Desktop" (not "unknown client 'cowork'").

- [ ] **Step 3: Commit**

```bash
git add scripts/configure_mcp.py
git commit -m "feat(mcp): add cowork alias for claude_desktop in configure_mcp.py"
```

---

### Task 2: Add Cowork plugin assembly block to `install.sh`

**Files:**
- Modify: `scripts/install.sh:471` (after the codex plugin block)

- [ ] **Step 1: Add Cowork plugin assembly block**

In `scripts/install.sh`, after the closing `fi` of the codex plugin block (line 471), add:

```bash
    # Install Cowork plugin if cowork was configured (ADR-503)
    if [[ "$INSTALL_FROM" == "cowork" ]] || [[ "$CONFIGURE_CLIENTS" == *"cowork"* ]]; then
        ASSEMBLER="${INSTALL_DIR}/skills/plugin-pack/scripts/plugin_assembler.py"
        if [ -f "$ASSEMBLER" ]; then
            print_step "Assembling Cowork plugin..."
            PYTHONPATH="${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/skills/plugin-pack/scripts" \
                uv run python "$ASSEMBLER" --target cowork --install || print_warning "Cowork plugin assembly skipped"
        fi
    fi
```

- [ ] **Step 2: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(install): add Cowork plugin assembly to install.sh"
```

---

### Task 3: Map `cowork` to `claude_desktop` for MCP config in `install.sh`

**Files:**
- Modify: `scripts/install.sh:441-447`

- [ ] **Step 1: Add platform alias before MCP config call**

Replace the block at lines 441-448:

```bash
    # Auto-configure MCP for originating platform (ADR-437)
    if [ -n "$INSTALL_FROM" ]; then
        CONFIGURE_SCRIPT="${INSTALL_DIR}/scripts/configure_mcp.py"
        if [ -f "$CONFIGURE_SCRIPT" ]; then
            print_step "Auto-configuring MCP for $INSTALL_FROM..."
            uv run python "$CONFIGURE_SCRIPT" --client "$INSTALL_FROM" || print_warning "MCP auto-config skipped"
        fi
    fi
```

with:

```bash
    # Auto-configure MCP for originating platform (ADR-437)
    if [ -n "$INSTALL_FROM" ]; then
        # Map platform aliases for MCP configuration
        MCP_CLIENT="$INSTALL_FROM"
        if [ "$INSTALL_FROM" = "cowork" ]; then
            MCP_CLIENT="claude_desktop"
        fi
        CONFIGURE_SCRIPT="${INSTALL_DIR}/scripts/configure_mcp.py"
        if [ -f "$CONFIGURE_SCRIPT" ]; then
            print_step "Auto-configuring MCP for $INSTALL_FROM..."
            uv run python "$CONFIGURE_SCRIPT" --client "$MCP_CLIENT" || print_warning "MCP auto-config skipped"
        fi
    fi
```

Note: the alias is done in both `install.sh` (for robustness) and `configure_mcp.py` (for direct `--client cowork` calls). Belt and suspenders.

- [ ] **Step 2: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(install): map cowork to claude_desktop for MCP wiring"
```

---

### Task 4: Add Cowork-specific post-install messaging to `install.sh`

**Files:**
- Modify: `scripts/install.sh:532-540`

- [ ] **Step 1: Replace generic "Next steps" with platform-aware message**

Replace lines 532-540:

```bash
    print_success "Environment ready."
    echo ""
    echo "Next steps:"
    echo "  1) Run Python commands with: uv run <command>"
    echo "  2) (Optional) Re-run tests anytime: LOCAL_RAG_REAL_OCR_DEPS=1 uv run pytest skills/knowledge/tests -q"
    echo "  3) Start augmenting your mind with Augur!"
    echo ""
    echo "Skills live in: ${INSTALL_DIR}/skills/"
    echo "User data lives in: ~/Vault/Augur/"
```

with:

```bash
    print_success "Environment ready."
    echo ""
    if [ "$INSTALL_FROM" = "cowork" ]; then
        echo "Next steps:"
        echo "  1) Restart Claude Desktop"
        echo "  2) Augur tools and skills will appear automatically"
        echo "  3) Try: /ask, /search, or /save"
    else
        echo "Next steps:"
        echo "  1) Run Python commands with: uv run <command>"
        echo "  2) (Optional) Re-run tests anytime: LOCAL_RAG_REAL_OCR_DEPS=1 uv run pytest skills/knowledge/tests -q"
        echo "  3) Start augmenting your mind with Augur!"
        echo ""
        echo "Skills live in: ${INSTALL_DIR}/skills/"
        echo "User data lives in: ~/Vault/Augur/"
    fi
```

- [ ] **Step 2: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(install): Cowork-specific post-install messaging"
```

---

### Task 5: Add `cowork` to `install.md` platform detection and routing

**Files:**
- Modify: `skills/onboard/install.md:9-24` (platform table)
- Modify: `skills/onboard/install.md:56-57` (routing logic)
- Modify: `dist/skills-pack/install.md:9-24` (same platform table, kept in sync)
- Modify: `dist/skills-pack/install.md:56-57` (same routing logic)

- [ ] **Step 1: Add cowork to platform detection table in `skills/onboard/install.md`**

After the line `| You are Claude Code or ~/.claude/ exists | claude-code |`, add:

```
| You are Claude Desktop (Cowork) | cowork |
```

- [ ] **Step 2: Add cowork routing after Step 1**

After the line `Store the detected value as PLATFORM for later steps.` (line 25), add:

```markdown

If PLATFORM is `cowork`, skip Step 2 and go directly to Step 4 (Full System Install).
Cowork requires the MCP server, so the skills-pack option does not apply.
```

- [ ] **Step 3: Apply the same changes to `dist/skills-pack/install.md`**

Repeat Steps 1 and 2 in `dist/skills-pack/install.md` (identical file, kept in sync).

- [ ] **Step 4: Commit**

```bash
git add skills/onboard/install.md dist/skills-pack/install.md
git commit -m "feat(onboard): add cowork platform to install.md with direct full-install routing"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Verify configure_mcp.py alias works**

```bash
uv run python scripts/configure_mcp.py --client cowork --check --verbose
```

Expected: mentions "Claude Desktop", exits 0 or 1 (not "unknown client").

- [ ] **Step 2: Verify plugin assembler runs from install.sh context**

```bash
source .venv/bin/activate && \
PYTHONPATH="$(pwd):$(pwd)/src/mcp:$(pwd)/skills/plugin-pack/scripts" \
    python skills/plugin-pack/scripts/plugin_assembler.py --target cowork --install
```

Expected: "Installed augur to Cowork desktop" in output.

- [ ] **Step 3: Verify install.md has cowork in the table**

```bash
grep -n "cowork" skills/onboard/install.md dist/skills-pack/install.md
```

Expected: both files show the cowork row in the platform table and the routing line.

- [ ] **Step 4: Commit any fixes if needed, then final commit**

```bash
git add -A && git commit -m "feat: Cowork self-service onboarding — end-to-end verified"
```
