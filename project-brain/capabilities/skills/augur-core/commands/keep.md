---
description: "Capture or persist anything. /keep <url|file|audio|image|folder|thought> to capture inbound. /keep --save <file> to persist generated artifacts. Merges /note and /save into one surface. Run bare /keep in a client session to reconcile the artifact you were just working on into Au-docs."
visibility: core
x-augur-export-command: true
---

# /keep

Unified capture and persistence command. One verb for "put this thing in the right place."

## Dispatch

Before selecting a note/save flow, plan the route with
`project-brain/capabilities/skills/ingest/scripts/keep_engine.py:plan_keep_route`.
The route planner is deterministic and local-first. If it returns
`warnings` containing `cloud-route-not-selected`, do not call cloud or Google
Drive tools unless the user explicitly confirms that cloud destination.

1. If `ARGUMENTS` is `--help` or `-h`: print the dispatch table and stop.
2. If `ARGUMENTS` is empty: route to **Session Reconcile** flow below.
3. If `ARGUMENTS` starts with `--save` or `artifact`: route to **Save** flow below.
4. Otherwise: route to **Note** flow below.

Every successful `/keep` run must be reportable as a `command.run.v1`
envelope: command `keep`, input class from `KeepRoute.kind`, chosen route from
`KeepRoute.route`, duration, warnings, and output path when available.

## Note Flow (inbound capture)

This is the former `/note` command. Follow the full dispatch logic in
`project-brain/capabilities/skills/ingest/commands/note.md` with the remaining arguments.
All note sub-dispatches (URL, file, audio, image, folder, thought, prompt,
voice-memo, email-drop) work identically.

## Save Flow (outbound persistence)

This is the former `/save` command. Follow the full logic in
`project-brain/capabilities/skills/augur-core/commands/save.md` with the remaining arguments.
Strip the `--save` prefix before passing to the save dispatcher.

Usage:
- `/keep --save --to project-augur report.md` -> save flow with explicit brain routing
- `/keep --save banner.png to venture` -> save flow
- `/keep --save report.pdf` -> save flow
- `/keep artifact <path>` -> save artifact flow

## Session Reconcile Flow (no arguments)

Reconciles the artifact the user was just working on in THIS session (slides,
docs, exports) into Au-docs, and cleans up stray intermediate versions. Spec:
`docs/superpowers/specs/2026-06-11-session-keep-artifact-reconcile-design.md`.

You (the client agent) own all judgment. The MCP tools (`artifact-locate`,
`artifact-keep`, `artifact-cleanup` on the augur-framework server) own the
atomic operations. Never use shell commands for any step of this flow — it
must work identically in shell-less clients (Claude Desktop, Cowork).
Steps 1–4 are read-only; step 5 is the approval gate — nothing is written or
deleted before explicit approval in THIS interaction (the bare /keep
invocation itself is not approval).

1. **Identify the artifact from session history**: name, format, export
   moments, topic. Multiple candidates → list them, let the user pick. No
   artifact in this session → say so and suggest `/keep <file|url|thought>`.
2. **Lane 1 — exported**: call `artifact-locate` with name hints from the
   session and a time window covering the session — use the tool default
   (48 hours); if the session clearly indicates an older export, or locate
   returns nothing, retry once with `hours_back=168` before falling to lane 2.
   It returns version families from `~/Downloads` and the Google Drive mirror
   with a `latest` candidate per family.
3. **Lane 2 — in-session content** (only if Lane 1 found nothing AND you can
   read the artifact content): call `artifact-keep` with `content_base64` +
   `filename`. Size-guarded: if `artifact-keep` returns success false with a
   size error (the error text names the size guard), fall to lane 3; other
   errors are NOT size rejections — report them honestly instead of retrying.
4. **Lane 3 — guaranteed fallback**: only if Lane 2 is unavailable or was
   rejected: ask the user to click download, then re-run `artifact-locate`
   in the same interaction.
5. **Propose ONE plan and get explicit approval** before any mutation:
   - latest version to file, and the Au-docs `target_folder` (chosen from
     session topic; existing domain folders like `venture-augur/`, `career/`),
   - optional canonical move to an EXISTING Drive-mirror folder matched by
     topic (skip if none fits — never create Drive folders),
   - the exact list of intermediate paths to trash (older family members,
     the Downloads leftover).
   Partial approval is valid ("file it but don't delete"). No approval → stop,
   nothing written, nothing deleted.
6. **Execute**: `artifact-keep` (filing + source card via the ingest packet
   lifecycle), then `artifact-cleanup` with ONLY the approved paths. Trash
   semantics are guaranteed (macOS Trash / Drive trash) — still, never pass a
   path the user did not see in the plan.
7. **Report**: canonical Au-docs path, source card path, cleanup receipt
   (moved/trashed), and anything skipped (mirror unmounted, lane-2 size
   rejection). If `drive_mirror_mounted` was false, say Drive was not swept.
   Report as a brief conversational summary (paths inline), never a raw JSON
   dump.

Honesty rules: locate finding nothing is a normal outcome — report what was
searched and offer lanes 2/3. A `needs_input` result from `artifact-keep`
means answer its questions, not retry blindly.

## Usage Examples

```bash
# Inbound capture (note flow)
/keep https://example.com/article
/keep ~/Downloads/paper.pdf
/keep --memo
/keep This is a thought I want to remember

# Outbound persistence (save flow)
/keep --save diagram.png to ai
/keep --save --to project-augur report.md
/keep --save report.pdf
/keep artifact output.html --hub dev

# Session reconcile
/keep
```
