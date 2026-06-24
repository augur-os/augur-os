# /auto-agent-digest

Compile violation signals into layered digest sections that get prepended to
`MEMORY.md`.

## What it does

1. Collects violation signals from git diffs, session corrections, and manual
   `/flag` events.
2. Scores directives into a hot tier and a warm tier.
3. Writes `digest-hot.md` and `digest-warm.md` into the memory directory for
   the memory assembler to prepend into `MEMORY.md`.

## Difficulty

- `d=0`: collect and score only
- `d=1`: write Hot digest
- `d=2`: write Hot + Warm digests and archive the journal

## Usage

```bash
/a-loops run auto-agent-digest
```
