---
title: project-command-kpi-pack-bakes-checkout-path
name: project-command-kpi-pack-bakes-checkout-path
description: Command KPI scenario packs bake the absolute project-root path of the
  generating checkout; generate the demo pack from the MAIN checkout or refs go stale
  after a worktree is cleaned
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_command_kpi_pack_bakes_checkout_path.md
source_hash: c0addf537b61dcff
---


`aug eval command-kpi-bootstrap` (project-brain/capabilities/skills/evals/scripts/command_kpi_bootstrap.py) writes the private scenario pack to `get_documents_dir()/evals/commands/scenarios/<run-id>.yaml` and bakes **absolute** `private_refs` / `required_source_refs` derived from `get_project_root()` — e.g. the in-repo `docs/references/command-quality-contract.md`.

If you bootstrap from inside a git worktree, those refs point at the ephemeral worktree path. After the worktree is merged and cleaned, the refs dangle and the `ask-project-canonical-commands` scenario fails `source_grounding` (file no longer exists → no sources loaded), which fails the whole `command-kpi-gate`. Observed 2026-05-24: the merged pack referenced `.worktrees/command-kpi-eval-loop/...command-quality-contract.md` and the fresh `demo-kpi-main-2` run scored 18/19 with that one fail.

**How to apply:** Always (re)generate the demo pack from the main checkout (`~/Projects/Augur`, `AUGUR_ROOT="$PWD"`). The pack is regenerable private data — delete stale packs and re-bootstrap rather than hand-patching refs. Note `_latest_scenario_path()` picks the lexicographically-last `*.yaml`, so a leftover stale pack can also shadow a freshly bootstrapped one. Related: [[feedback-agent-isolation-unsafe]], [[project-worktree-dashboard-port-verification]].
