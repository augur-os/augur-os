---
status: Implemented
date: '2026-02-24'
deciders:
- Augur project team
related:
- ADR-087 (data dir elimination)
- ADR-126 (generic plugin template)
hub: null
tags:
- binary
- asset
- write
- support
- augur
superseded_by: null
---

# ADR-142: Binary Asset Write Support for Augur File Tools

## Context

Augur's MCP file tools (`file-write`, `file-read`) only support text content. The `file-write` tool accepts `content: str` and writes via `open(path, "w", encoding=encoding)` — pure text mode. There is no mechanism to write binary files (images, PDFs, slides, zip archives) through MCP.

This creates a hard wall when AI agents attempt to save generated or retrieved assets into plugin asset directories. Real-world failure scenario from Claude Desktop:

```
User: Save this banner image to the venture-augur assets folder
Agent: Found it. Your banners live in plugins/professional/skills/venture-augur/assets/images/.
       Let me save it there.
       [Get base64 of banner to write via augur file tools]  ← FAILS
       [Get base64 of banner to write via augur file tools]  ← RETRIES
       [Get base64 of banner to write via augur file tools]  ← RETRIES AGAIN
```

The agent has the binary data (as base64), knows the target path, but has no tool to decode and write it. The `file-write` tool would corrupt the data by treating base64 as text or fail on encoding.

**Current state:**
- `FileWriteInput.content` is `str` — no bytes support
- `write_file_impl()` opens files in text mode (`"w"`)
- Zero base64 handling in `src/mcp/augur_mcp/infrastructure/files.py`
- Asset directories exist across 10+ plugins (`plugins/*/skills/*/assets/`)
- Binary files (images, PDFs, zips) are managed only via direct filesystem ops outside MCP

**Scope of the problem:**
- Claude Desktop, Claude Code, and any MCP client cannot write binary assets
- Agents must fall back to shell commands (`base64 -d | tee`) which bypasses security sandboxing
- No asset metadata tracking — agents can't query what assets exist by type

## Decision

### 1. New `file-write-binary` MCP Tool

Add a dedicated binary write tool alongside the existing text `file-write`. Keeping them separate avoids complicating the text tool's interface and makes the binary nature explicit in the tool name.

**Input model:**

```python
class FileWriteBinaryInput(BaseModel):
    path: str           # Target file path (within allowed repos)
    content_base64: str # Base64-encoded binary content
    repo: RepoTarget = RepoTarget.AUTO
    create_backup: bool = True
    create_dirs: bool = True
```

**Implementation:**
- Decode `content_base64` via `base64.b64decode()` with validation
- Write via `open(path, "wb")` — binary mode
- Reuse existing atomic write pattern (temp file + rename)
- Reuse existing path security (`resolve_secure_path`, `validate_path_within_roots`)
- Size limit: 50MB per write (prevents accidental multi-GB writes)

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/files.py` — add `FileWriteBinaryInput`, `write_binary_file_impl()`, register `file-write-binary` tool

### 2. Extend `file-read` with Binary Mode

Add an optional `binary` flag to `file-read` that returns base64-encoded content instead of text lines. This lets agents round-trip binary files (read → transform → write back).

**Changes to `FileReadInput`:**

```python
class FileReadInput(BaseModel):
    # ... existing fields ...
    binary: bool = False  # If True, return content as base64 string
```

**Behavior when `binary=True`:**
- Read via `open(path, "rb")`
- Return `{"content_base64": "<base64>", "size_bytes": N, "mime_type": "image/png"}`
- Ignore `offset`/`limit` (line-based pagination doesn't apply to binary)
- Size limit: 50MB (same as write)
- Auto-detect MIME type from file extension

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/files.py` — extend `FileReadInput`, add binary branch to `read_file_impl()`

### 3. Asset Type Validation (Optional Safety Layer)

When writing to `*/assets/*` paths, validate file extension matches content:

| Extension | Expected magic bytes |
|-----------|---------------------|
| `.png` | `\x89PNG` |
| `.jpg`/`.jpeg` | `\xff\xd8\xff` |
| `.pdf` | `%PDF` |
| `.zip` | `PK\x03\x04` |
| `.gif` | `GIF8` |
| `.webp` | `RIFF....WEBP` |

This prevents agents from accidentally writing corrupted files (e.g., writing raw base64 text as a `.png`). Validation is a warning, not a hard block — agents may write novel formats.

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/files.py` — add `_validate_asset_magic_bytes()` helper

### 4. MCP Tool Description Update

Update the `file-write-binary` tool description to guide agents:

```
Write binary content (images, PDFs, archives) to file.
Content must be base64-encoded. Use this for non-text files.
For text files, use file-write instead.
```

## Consequences

**Positive:**
- Agents can save generated/retrieved binary assets (images, PDFs, slides) through MCP
- All writes go through the security sandbox (`resolve_secure_path`, `validate_path_within_roots`)
- Round-trip support: read binary → process → write binary
- Magic byte validation catches common corruption errors
- No changes to existing `file-write` behavior — fully backward compatible

**Negative:**
- Base64 encoding adds ~33% overhead (a 10MB image becomes ~13.3MB in the MCP message)
- 50MB limit means very large assets (videos, datasets) still need direct filesystem access
- Adds one more tool to the MCP tool surface area

**Neutral:**
- Text `file-write` remains unchanged — no migration needed
- Existing asset directories require no restructuring

## Implementation Order

```
Phase 1: Binary Write Tool
├── Step 1: Add FileWriteBinaryInput model to files.py
├── Step 2: Implement write_binary_file_impl() with atomic write pattern
├── Step 3: Register file-write-binary tool in register_file_tools()
└── Step 4: Add magic byte validation helper

Phase 2: Binary Read Support (depends on Phase 1)
├── Step 5: Extend FileReadInput with binary flag
└── Step 6: Add binary branch to read_file_impl()

Phase 3: Verification (depends on Phase 2)
├── Step 7: Write tests for binary write (PNG, PDF, ZIP round-trip)
├── Step 8: Write tests for binary read
├── Step 9: Test magic byte validation (valid + mismatch)
└── Step 10: Verify existing text file-write/file-read unchanged
```

## Alternatives Considered

### 1. Extend Existing `file-write` with an `encoding: "base64"` Flag

Add a special encoding value to the existing tool instead of a new tool.

**Rejected because:**
- Overloads the `encoding` parameter which currently means text encoding (utf-8, latin-1, etc.)
- `content: str` field semantics change based on encoding — confusing for agents
- Agents may accidentally use `encoding: "base64"` for text files
- Separate tools with explicit names are clearer for LLM tool selection

### 2. Accept Raw Bytes in `file-write` Content Field

Use a union type `content: str | bytes`.

**Rejected because:**
- MCP protocol transmits JSON — no native bytes type
- Pydantic model validation would need complex discriminators
- Every MCP client would need to handle the union differently

### 3. Stream Binary Content via Chunked Writes

Add `file-write-chunk` for streaming large binaries in pieces.

**Rejected because:**
- Adds significant complexity (chunk ordering, reassembly, resume)
- 50MB base64 limit covers 99% of asset use cases (images, PDFs, slides)
- Can be added later if streaming is needed for video/dataset use cases

## References

- `src/mcp/augur_mcp/infrastructure/files.py` — Current file tools implementation
- `plugins/professional/skills/venture-augur/assets/` — Example asset directory (images, logos, videos)
- `plugins/ai/skills/mcp-app-factory/scripts/process_icon.py` — Existing image processing (uses PIL directly, not MCP)
- Python `base64` module docs: standard library base64 encoding/decoding

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-142: Binary Asset Write Support for Augur File Tools**.

Read the full ADR: `docs/decisions/ADR-142-binary-asset-write-support.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-142-binary-assets", description="Implementing ADR-142: Binary Asset Write Support")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-142-binary-assets", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-142 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-142-binary-assets`

#### Phase 1: Binary Write Tool
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `FileWriteBinaryInput` Pydantic model with `content_base64: str`, `path`, `repo`, `create_backup`, `create_dirs` fields. Add `import base64` to imports. | `src/mcp/augur_mcp/infrastructure/files.py` |
| 1.2 | developer | medium | Implement `write_binary_file_impl()` — decode base64, validate size ≤50MB, write via `open(path, "wb")`, reuse atomic temp+rename pattern from `write_file_impl()`, reuse `resolve_secure_path`/`validate_path_within_roots` | `src/mcp/augur_mcp/infrastructure/files.py` |
| 1.3 | developer | medium | Register `file-write-binary` tool in `register_file_tools()` with proper annotations (`readOnlyHint: False`, `destructiveHint: False`), wire to `write_binary_file_impl()` | `src/mcp/augur_mcp/infrastructure/files.py` |
| 1.4 | developer | low | Add `_validate_asset_magic_bytes(data: bytes, extension: str) -> tuple[bool, str]` helper — check PNG/JPG/PDF/ZIP/GIF/WEBP magic bytes, return `(valid, message)`. Log warning on mismatch but don't block write. | `src/mcp/augur_mcp/infrastructure/files.py` |

#### Phase 2: Binary Read Support
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Extend `FileReadInput` with `binary: bool = False` field. Add binary branch to `read_file_impl()` — when `binary=True`, read via `"rb"`, return `content_base64` + `size_bytes` + auto-detected `mime_type` from extension. Enforce 50MB size limit. | `src/mcp/augur_mcp/infrastructure/files.py` |
| 2.2 | developer | low | Update `file-read` tool description in `register_file_tools()` to mention binary mode: "Set binary=True to read non-text files as base64." | `src/mcp/augur_mcp/infrastructure/files.py` |

#### Phase 3: Verification
**Strategy**: PIPELINE (depends on Phase 2)
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | medium | Write tests: binary write round-trip (create PNG/PDF/ZIP via base64, read back, verify identical), magic byte validation (valid PNG, mismatched extension), size limit rejection, text file-write unchanged | `tests/src/mcp/test_file_binary.py` |
| 3.2 | validator | low | Run `pytest tests/src/mcp/` to verify all tests pass, both new and existing |
| 3.3 | architect | low | Verify ADR intent matches implementation — check tool names, parameter shapes, security enforcement, and that existing text tools are unchanged |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/mcp/`)
- [ ] `file-write-binary` tool registered and callable
- [ ] `file-read` supports `binary=True` mode
- [ ] Magic byte validation warns on mismatch
- [ ] Existing `file-write` and `file-read` behavior unchanged
- [ ] No orphaned files or broken references
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-142-binary-asset-write-support.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
