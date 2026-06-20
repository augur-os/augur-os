---
description: Validate self-heal daemon health and clear stuck journal entries
visibility: auto
---

# auto-heal-validate

Validate self-heal daemon health and clear stuck journal entries. Daemon-managed (nightly loop, tier 2).

## Scan

Checks self-heal journal for stuck entries, orphaned fix attempts, and daemon health indicators.

## Fix

Clears stuck journal entries and resets orphaned fix states to allow retry.
