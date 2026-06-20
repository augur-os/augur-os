# Gemini Extension Support for Augur Plugin Pack - Design Spec

**Date:** 2026-04-19  
**Status:** Proposed  
**Scope:** Add Gemini CLI extension support to the Augur plugin-pack pipeline so Gemini receives the same bundled Augur capability surface that Codex and Claude receive today.

---

## Problem

Augur currently exposes capabilities to clients through two different mechanisms:

- explicit command wrappers, such as `/dev-loops`, generated into project-local client surfaces
- plugin-pack bundles for higher-level Augur capabilities, currently targeting Codex and Claude Desktop Cowork

This split is visible in the current `/ask` behavior. Codex and Claude can see Augur's bundled `ask` command through the Augur plugin package, while Gemini only receives explicitly exported command wrappers such as `dev-loops`. Gemini is not missing `/ask` because its local skill discovery is broken. It is missing `/ask` because Augur does not currently assemble or install an Augur bundle for Gemini CLI.

Gemini CLI supports extensions that can package MCP servers, custom commands, context, and agent skills. Augur should use that native extension mechanism instead of treating Gemini as a loose collection of generated `.gemini/skills` files.

---

## Goals

- Add Gemini as a first-class `plugin-pack` target beside `codex` and `cowork`.
- Package Augur MCP access for Gemini with `--client-id gemini`.
- Package Augur core commands (`ask`, `search`, `save`) as Gemini custom commands.
- Package selected Augur skills in Gemini's extension `skills/` directory.
- Make normal sync/install behavior as close as practical to the current Codex and Claude plugin-pack behavior.
- Preserve the existing explicit command-wrapper path for operational repo commands such as `/dev-loops`.
- Keep Gemini extension cleanup surgical and limited to Augur-managed extension files.

---

## Non-Goals

- Do not remove `.gemini/skills` command wrappers for explicitly exported repo commands.
- Do not redesign plugin-pack filtering for all targets.
- Do not move command behavior into Gemini-only implementations.
- Do not introduce a central registry for command duplication.
- Do not publish to an external Gemini extension registry in this change.
- Do not require users to manually maintain `~/.gemini/settings.json` for Augur MCP once the extension is installed.

---

## Decision

Implement a native Gemini extension target in `plugin-pack`.

The target should generate a complete local Gemini extension bundle and install it into Gemini's native extension directory. This makes Gemini match the existing Codex and Claude model: Augur owns the bundle assembly and installation lifecycle, while the client loads the installed package natively.

The extension should expose user-facing Augur plugin commands as namespaced Gemini slash commands:

- `/augur:ask`
- `/augur:search`
- `/augur:save`

Namespacing avoids collisions with user-defined Gemini commands and makes the command origin explicit. Explicit repo command wrappers such as `/dev-loops` should continue to be generated separately through `x-augur-export-command: true`.

---

## Target Behavior

The plugin-pack CLI should support:

```bash
python staging/r3/skills/plugin-pack/scripts/plugin_assembler.py --target gemini
python staging/r3/skills/plugin-pack/scripts/plugin_assembler.py --target gemini --install
```

`--target gemini` assembles the extension under `build/gemini/`.

`--target gemini --install` replaces only Augur's managed Gemini extension at:

```text
~/.gemini/extensions/augur/
```

The normal `sync-agents` lifecycle should also run the Gemini plugin adapter when Gemini is enabled, in the same spirit as `CodexPluginAdapter` and `CoworkAdapter`.

---

## Extension Output

The assembled bundle should be:

```text
build/gemini/
└── extensions/
    └── augur/
        ├── gemini-extension.json
        ├── GEMINI.md
        ├── skills/
        │   ├── ask/
        │   │   └── SKILL.md
        │   ├── search/
        │   │   └── SKILL.md
        │   └── ...
        └── commands/
            └── augur/
                ├── ask.toml
                ├── search.toml
                └── save.toml
```

The installed bundle should have the same internal shape at `~/.gemini/extensions/augur/`.

---

## Gemini Manifest

`gemini-extension.json` should include:

```json
{
  "name": "augur",
  "version": "<version>",
  "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
  "contextFileName": "GEMINI.md",
  "mcpServers": {
    "augur": {
      "command": "<python>",
      "args": ["-m", "augur_mcp", "--client-id", "gemini"],
      "cwd": "<project-root>",
      "env": {
        "AUGUR_ROOT": "<project-root>",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "<project-root>:<project-root>/src/mcp"
      }
    }
  }
}
```

The manifest should not include trust or allow-list policy. Gemini ignores or constrains extension trust decisions, and Augur should not try to bypass client security prompts through the extension package.

---

## Commands

Gemini custom commands use TOML command definition files. The Gemini formatter should write command files under:

```text
commands/augur/<command>.toml
```

This creates namespaced commands such as `/augur:ask`.

Each file should include:

```toml
description = "Ask your second brain any question"
prompt = """
<command instructions>

User arguments:
{{args}}
"""
```

The command prompt should be generated from the same plugin-pack command profile source used for Codex and Cowork initially. As a later cleanup, plugin-pack should derive command bodies from `skills/augur-core/commands/*.md` so `ask`, `search`, and `save` are not maintained in two places.

---

## Skills

The Gemini extension should include selected Augur skills in:

```text
skills/<skill>/SKILL.md
```

Initial filtering should match the Codex profile because both targets are local developer-agent environments:

- hubs: `brain`, `career`, `life`, `studio`, `command`
- excluded prefixes: `auto-`, `client-`
- excluded skills: the current common plugin-pack exclusions

The formatter should reuse `transform_skill_md()` so skills are sanitized in the same way as existing plugin-pack outputs.

---

## Context

The extension should include a small `GEMINI.md` file that explains the Augur extension surface:

- Augur is local-first and uses the `augur` MCP server.
- Use `/augur:ask` for reflective second-brain questions.
- Use `/augur:search` for knowledge retrieval.
- Use `/augur:save` for saving knowledge or assets.
- Operational project commands such as `/dev-loops` may still come from project-local `.gemini/skills` wrappers.

This context should be concise. The repo-level `.gemini/GEMINI.md` remains the canonical project instruction surface.

---

## Components

### `staging/r3/skills/plugin-pack/scripts/profiles.py`

Add `GEMINI_PROFILE` and include it in `_PROFILES`.

The first profile should match `CODEX_PROFILE`. If later Gemini-specific differences appear, they should be localized to the Gemini profile instead of branching inside the formatter.

### `staging/r3/skills/plugin-pack/scripts/formatters/gemini.py`

Add `GeminiFormatter(BaseFormatter)`.

Responsibilities:

- write `gemini-extension.json`
- write `GEMINI.md`
- write `skills/<name>/SKILL.md`
- write `commands/augur/*.toml`
- install into `~/.gemini/extensions/augur`
- cleanly replace only the Augur extension directory

### `staging/r3/skills/plugin-pack/scripts/formatters/__init__.py`

Export `GeminiFormatter`.

### `staging/r3/skills/plugin-pack/scripts/plugin_assembler.py`

Register the `gemini` formatter in `_FORMATTERS` and update usage text.

### `skills/ai/scripts/sync_agents/adapters/gemini_plugin.py`

Add a Gemini plugin bundle adapter parallel to `CodexPluginAdapter`.

Responsibilities:

- `adapter_name = "gemini_plugin"`
- detect Gemini through `shutil.which("gemini")` or `~/.gemini`
- assemble `target="gemini"` into `build/gemini`
- install the Gemini extension
- report managed files for cleanup:
  - `build/gemini/`
  - `~/.gemini/extensions/augur/`

Cleanup should remove only `~/.gemini/extensions/augur/` and `build/gemini/`.

### `skills/ai/scripts/sync_agents/engine.py`

Register `GeminiPluginAdapter` in `_get_all_adapters()`.

### `skills/ai/scripts/sync_agents/adapters/__init__.py`

Export `GeminiPluginAdapter`.

### `skills/ai/scripts/sync_agents/__init__.py`

Include `gemini-plugin` in supported client normalization if the CLI supports targeting adapters by name.

### `staging/r3/skills/plugin-pack/SKILL.md`

Document the new target, output format, and usage.

### `apps/dashboard/app/api/plugin-pack/route.ts`

Update the read-only target list and pipeline text so the dashboard reports Gemini as a supported plugin-pack target.

---

## Data Flow

1. `sync-agents` initializes adapters.
2. If Gemini and the Gemini plugin adapter are enabled, `GeminiPluginAdapter.generate_mcp_config()` runs.
3. The adapter resolves the staged or live `plugin-pack` skill through `find_skill_dir()`.
4. The adapter imports `plugin_assembler`.
5. `assemble("gemini", build/gemini)` selects `GEMINI_PROFILE`.
6. The assembler discovers eligible skills, transforms their `SKILL.md`, and passes them to `GeminiFormatter`.
7. `GeminiFormatter` writes the extension bundle.
8. `install("gemini", output, version)` replaces `~/.gemini/extensions/augur/`.
9. Gemini CLI loads the extension on the next session restart.

---

## Error Handling

- If Gemini CLI is not installed and `~/.gemini` does not exist, the adapter should report not installed and skip installation.
- If `plugin-pack` cannot be found, the adapter should raise the same clear `FileNotFoundError` pattern used by Codex and Cowork adapters.
- If `~/.gemini/extensions/augur` is a symlink or file, cleanup should remove it before copying the managed extension.
- If `~/.gemini/extensions` is missing but Gemini is detected, install should create the directory.
- If installation succeeds, log that Gemini must be restarted for extension changes to apply.

---

## Security and Safety

- The formatter should not write allow/trust settings into Gemini configuration.
- Generated command TOML should avoid shell execution injection features such as `!{...}`.
- Generated command prompts should pass user input through `{{args}}` instead of embedding shell commands.
- Cleanup must be path-specific and must never delete all of `~/.gemini/extensions`.
- The extension should use the existing local MCP server and environment model rather than duplicating privileged behavior in command files.

---

## Relationship to Existing Command Export

This design does not replace `x-augur-export-command: true`.

Use command export for project operational commands that should appear as direct client-local entries:

- `/dev-loops`
- `/dev-merge`

Use the Gemini extension for Augur plugin capabilities:

- `/augur:ask`
- `/augur:search`
- `/augur:save`
- Augur MCP-backed knowledge tools
- selected second-brain skills

This keeps operational project commands and packaged product capabilities separate.

---

## Testing

Add focused tests in the existing plugin-pack and sync-agent test areas.

### Plugin-Pack Tests

- `test_gemini_profile_matches_codex_initial_scope`
- `test_get_profile_returns_gemini`
- `test_gemini_formatter_writes_manifest_with_mcp_server`
- `test_gemini_formatter_uses_gemini_client_id`
- `test_gemini_formatter_writes_namespaced_toml_commands`
- `test_gemini_formatter_writes_skills`
- `test_gemini_formatter_install_replaces_only_augur_extension`
- `test_assemble_gemini`

### Sync-Agent Tests

- `test_gemini_plugin_adapter_managed_files`
- `test_gemini_plugin_adapter_detect_installed`
- `test_gemini_plugin_adapter_generate_mcp_config_installs_extension`
- `test_all_adapters_include_gemini_plugin`
- `test_disabled_gemini_plugin_cleanup_removes_only_augur_extension`

### Manual Verification

After implementation:

```bash
python staging/r3/skills/plugin-pack/scripts/plugin_assembler.py --target gemini --install
test -f ~/.gemini/extensions/augur/gemini-extension.json
test -f ~/.gemini/extensions/augur/commands/augur/ask.toml
test -f ~/.gemini/extensions/augur/skills/ask/SKILL.md
```

Then restart Gemini CLI and verify:

- `/extensions list` shows Augur.
- `/augur:ask` is available.
- the Augur MCP server is available to the session.

---

## Rollout

1. Add the formatter/profile with tests.
2. Add the sync adapter with tests.
3. Update plugin-pack docs and dashboard metadata.
4. Run plugin-pack unit tests.
5. Run sync-agent adapter lifecycle tests.
6. Assemble and install the Gemini extension locally.
7. Restart Gemini CLI and verify extension visibility.

---

## References

- Gemini CLI extensions documentation: `https://google-gemini.github.io/gemini-cli/docs/extensions/`
- Gemini CLI extension reference: `https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/reference.md`
- Gemini CLI custom commands documentation: `https://geminicli.com/docs/cli/custom-commands/`
- Existing plugin-pack owner: `staging/r3/skills/plugin-pack/SKILL.md`
- Existing Codex formatter: `staging/r3/skills/plugin-pack/scripts/formatters/codex.py`
- Existing Cowork formatter: `staging/r3/skills/plugin-pack/scripts/formatters/cowork.py`

