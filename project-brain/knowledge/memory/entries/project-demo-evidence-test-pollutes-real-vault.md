---
title: project-demo-evidence-test-pollutes-real-vault
name: project-demo-evidence-test-pollutes-real-vault
description: A demo-evidence test writes to the REAL vault notes/demo/ instead of
  tmp_path — test-isolation bug found during /dev merge full
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_demo_evidence_test_pollutes_real_vault.md
source_hash: '3470578793411254'
---


During a `/dev merge full` (2026-05-25) the vault repo showed an untracked `notes/demo/evidence/meeting-transcript-aug-demo-smoke-<ts>.md`. Its frontmatter proved it was **test pollution**, not user data: `type: demo-evidence`, `demo_command: aug demo-smoke`, and `source_file_path: /private/var/folders/.../pytest-of-<user>/pytest-402/test_demo_run_record_evidence_0/...` (a pytest tmp dir).

**The bug:** the demo-evidence test (`test_demo_run_record_evidence`, likely under the `ingest` skill which owns `demo-smoke`/`demo-reset`/`demo-readiness`) writes demo evidence to the **real** vault (`get_vault_dir()/notes/demo/evidence/`) instead of an isolated `tmp_path`. So running the test suite pollutes the user's actual vault. The artifact was removed (untracked, junk) to leave the vault clean, but the test itself is unfixed.

**Fix:** make the demo-evidence test (and the `demo-smoke` evidence-writer it exercises) honor an injectable/`AUGUR_VAULT`-overridden evidence dir so tests write to tmp, not the live vault. **Why:** test runs must never mutate real user data (rule 5 / data safety). **How to apply:** find the evidence-dir resolution in the demo-smoke writer, add a param/env override, point the test at `tmp_path`. Watch for this when running the suite from the main checkout (it dirties the live vault). Related: [[project-test-suite-topology]], [[email-drop-ingest-routes-personal-emails-to-shared-vault-scope]] (another background-writes-to-vault issue).
