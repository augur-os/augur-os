---
status: Implemented
date: 2026-05-10
deciders:
  - gsannikov
related:
  - ADR-583
hub: null
tags:
  - shell
  - tooling
  - worktree
  - codex
superseded_by: null
spec_file: 2026-05-10-xa-main-or-worktree-launch-design.md
plan_file: 2026-05-10-xa-main-or-worktree-launch.md
---

# ADR-617: XA — Main or Worktree Launch

> **ADR-617 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Replace the `~/.zshrc` alias string with a repo-owned `scripts/xa-launch.sh` entrypoint. Prompt every run for `main` or `new worktree`; reject invalid answers. In `main` mode: verify branch, fetch `origin/main`, auto-stash dirty trees, fast-forward, restore stash, then launch Codex via `codex` on the canonical project root. In `new worktree` mode: create a fresh worktree off `origin/main` under a configurable parent directory, branch-name validated, then launch Codex inside it. The launcher is the single safe path for starting a Codex session — no more accidental Codex launches against stale `main` or against the wrong working tree.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-10-xa-main-or-worktree-launch-design.md`](../superpowers/specs/2026-05-10-xa-main-or-worktree-launch-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-10-xa-main-or-worktree-launch.md`](../superpowers/plans/2026-05-10-xa-main-or-worktree-launch.md)

## Status notes

Index ADR reconstructed on 2026-05-12 from the existing spec + plan to align with the new thin-index ADR workflow (the original `/adr write` run that produced this ADR's spec and plan did not generate the markdown index file). No design content was changed in reconstruction.

## Related

- ADR-583 — Worktree Launcher and Lifecycle Generalization
