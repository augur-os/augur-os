---
id: run-loop-cycle
description: Trigger a single scan+fix cycle for a specific adaptive loop
skill: daemon
tags: []
---

Ask which loop to run (self-heal, code-quality, hardening, knowledge-enrichment, command-evolution). Then execute: PYTHONPATH="$PWD/project-brain:$PWD:$PWD/src/mcp" python3 project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py --run {loop_name}. Use --run-all only when the user asks to run all loops. Report results.
