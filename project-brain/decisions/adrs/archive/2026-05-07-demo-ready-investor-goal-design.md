---
title: Demo-Ready Investor Goal Design
date: 2026-05-07
status: ready-for-review
scope: goal-definition
---

# Demo-Ready Investor Goal Design

## Purpose

Define what "demo-ready" means for the AI PC Brain Inbox investor/product demo.

The goal is not to create a fake demo surface. The goal is to make the real local-first Augur workflow reliable enough that a seeded investor walkthrough can run end to end on this Windows AI PC without manual repair.

## Primary Audience

The primary audience is an investor or product evaluator.

The demo should feel polished, concrete, and memorable. Technical proof matters, but it should support the product story rather than become the whole demo.

## Demo-Ready Goal

Augur can run a real, repeatable investor demo where curated Desktop inbox files go through the actual production pipeline:

- local extraction, OCR, transcription, and local agent attempts run first
- airplane mode blocks cloud escalation completely
- one controlled hard file performs real cloud escalation when airplane mode is off
- files are actually routed, renamed, moved or copied according to the workflow policy
- source cards and extracted or transcribed artifacts are actually written
- RAG indexing/search visibility is actually updated from the run output
- Brain Inbox and Brain Insights show evidence from the real run

## Product Story

The walkthrough has three connected beats.

1. Messy Desktop files become organized brain knowledge.
2. Airplane mode proves local-first AI behavior on the laptop.
3. A meeting MP3 becomes transcript, summary, action items, and searchable memory.

These should feel like one workflow, not three unrelated feature checks.

## Seeded But Real

Prepared demo inputs are allowed and expected. The demo may use a fixture pack and reset script so the walkthrough is stable.

The run itself must still use the same production path a user would use. Seeded inputs are not permission to hardcode outputs or bypass real processing.

## Non-Cheating Rules

The demo must not rely on:

- hardcoded file results
- fake dashboard counters
- prewritten output presented as generated output
- mocked cloud escalation
- manual file moves, renames, or edits during the walkthrough
- direct dashboard data bypassing MCP
- silent failure fallbacks that pretend weak extraction succeeded

If local OCR, transcription, routing, indexing, or cloud escalation fails, the UI and run evidence must show the failure or review-needed state honestly.

## Required Demo Modes

### Airplane Mode On

The same seeded inbox is processed with airplane mode enabled.

Expected behavior:

- no cloud vision, audio, text, or classification call is made
- local deterministic extraction and local transcription are allowed
- local Ollama vision or local agent escalation is allowed
- unresolved low-confidence files become review-needed
- the run evidence proves cloud calls stayed at zero

### Airplane Mode Off

The seeded inbox is processed with airplane mode disabled.

Expected behavior:

- local-first ordering still happens
- one controlled hard document escalates to cloud through Augur's real supported escalation path
- the cloud call has an explicit escalation reason
- the UI shows the cloud call count and the file-level reason
- the resulting source card and RAG entry are produced from the real output

## Required Demo Artifacts

The demo-ready system needs:

- a curated fixture pack with mixed Desktop files
- a reset path that prepares a clean demo state
- at least one text PDF or Office-like document
- at least one scanned or photo document that is hard enough to exercise review or escalation
- at least one MP3 meeting recording
- generated source cards with YAML frontmatter
- extracted Markdown or transcript artifacts linked from source cards
- run records with file-level evidence
- visible Brain Inbox and Brain Insights payoff
- a readiness check that fails before the walkthrough if required capabilities are missing

## Acceptance Criteria

The goal is met when a fresh reset plus the normal Brain Inbox workflow can complete the demo without manual repair.

The completed run must prove:

- files were scanned from the configured Desktop inbox
- stable files were consumed and unstable files were skipped honestly
- destination routing and normalized filenames came from the workflow
- source cards were written to the brain/vault location
- extracted text, OCR output, or transcript artifacts were produced
- the MP3 produced transcript, summary, action items, and searchable memory
- RAG indexing/search visibility includes the new run output
- airplane mode on blocked every cloud escalation
- airplane mode off allowed exactly the controlled real cloud escalation
- Brain Inbox and Brain Insights display real run data, not fixture-only UI state

## Verification Standard

Demo readiness requires verification at three levels.

1. Backend verification proves the ingestion, extraction, policy, source-card, and RAG handoff logic.
2. Runtime smoke verification runs the seeded demo reset and consume path against real files.
3. Browser verification proves Brain Inbox and Brain Insights load interactively and show real run evidence.

The verification output should be concise enough to use as a pre-demo checklist.

## Non-Goals

This goal does not require:

- background filesystem watching
- perfect OCR or transcription for arbitrary files
- broad cloud-provider benchmarking
- destructive cleanup of user files
- a public marketing page
- a video-only demo replacing the live seeded run

## Follow-On Work

After this goal is approved, the implementation plan should identify the smallest set of gaps between the current merged AI PC Brain Inbox work and this demo-ready standard.

The plan should prioritize real end-to-end proof over more UI polish.
