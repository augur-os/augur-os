---
description: Flag a decision violation for the agent-digest nightly loop
visibility: public
---

# flag

Manually flag when an agent violated a known decision. The violation is
recorded in the event journal and will appear in the next nightly digest
with boosted priority.

## Usage

/flag "<description>" [--rule <rule_id>] [--adr <ADR-NNN>]

## Examples

/flag "agent added to centralized config again" --adr ADR-163
/flag "used emoji in commit message"
/flag "edited generated file directly" --rule no_generated_edits

## Options

- `--rule <id>` — Map directly to a directive ID from directive-map.yaml
- `--adr <ADR-NNN>` — Map to a specific ADR number
- If neither flag is provided, the system infers the directive from description text
