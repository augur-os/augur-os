# Cross-Platform Text-to-Speech for Augur

**Date:** 2026-03-29
**Status:** Approved
**Context:** Augur needs a cross-platform TTS capability — macOS `say` equivalent on Windows — integrated as both an MCP tool and dashboard UI component.

## Decision

Use OS-native TTS engines exclusively. No ML models, no cloud APIs, no GPU requirements.

- macOS: `say` command (built-in since OS X 10.0)
- Windows: `pyttsx3` wrapping SAPI/OneCore (single pip dependency)
- OS default voice, rate, volume — no user configuration

## Architecture

```
Dashboard UI ──> /api/mcp/tool ──> MCP "speak" tool ──> tts_engine.py ──> OS native
Skills/Agents ─────────────────> MCP "speak" tool ──> tts_engine.py ──> OS native
```

Single data path. No queue — new requests interrupt current speech.

## MCP Tool

```python
@mcp.tool(name="speak")
def speak(text: str, stop: bool = False) -> dict:
    """Speak text aloud using the OS native TTS engine.

    If stop=True, kills any current speech and returns without speaking.
    If speech is already playing, interrupts it before starting new text.
    """
```

Response shapes:

```python
{"status": "speaking", "platform": "macos", "length": 142}
{"status": "stopped"}
{"status": "error", "message": "TTS not available on this platform"}
```

## Platform Backends

### macOS

```python
subprocess.run(["killall", "say"], capture_output=True)  # interrupt
process = subprocess.Popen(["say", text])                 # speak
```

Zero dependencies. `killall say` handles interrupt.

### Windows

```python
import pyttsx3
engine = pyttsx3.init()
engine.stop()        # interrupt
engine.say(text)
engine.runAndWait()
```

Single dependency: `pyttsx3`. Works out of box on Windows 10+.

### Unsupported Platforms

Returns `{"status": "error", "message": "TTS not available on this platform"}`. Linux `espeak` support can be added later.

## Dashboard Component

Reusable `ReadAloudButton`:

```tsx
<ReadAloudButton text={blockContent} />
```

- Idle: speaker icon
- Speaking: stop icon, click to interrupt
- Uses `useMcpMutation("speak", { text })` and `useMcpMutation("speak", { stop: true })`
- Added to block renderer action bar for blocks with `readAloud: true` config
- No dedicated page — utility component only

## Skill Structure

```
skills/tts/
├── SKILL.md              # x-augur-hub: command, x-augur-type: service
├── scripts/
│   └── tts_engine.py     # cross-platform TTS wrapper
├── commands/
│   └── speak.md          # /speak slash command docs
├── augur/
│   └── dashboard/
│       └── components/
│           └── ReadAloudButton.tsx
└── assets/
    └── seeds/
        └── _seed.yaml
```

## Wiring

- MCP tool registered in `src/mcp/__init__.py` — imports `tts_engine.speak()`
- Dashboard component via `@skill/tts/...` alias
- Block renderer: one-line addition for `ReadAloudButton` when `readAloud` present
- `/speak <text>` slash command calls MCP tool directly

## Dependencies

- macOS: none
- Windows: `pyttsx3` as optional in `pyproject.toml`

## Interrupt Behavior

Any new `speak` call kills current speech before starting. No queue, no state machine.

## Top Use Cases

1. Read dashboard content aloud (daily briefings, ADRs, attention items)
2. Notification announcements (build failures, attention items)
3. Hands-free agent responses (`/ask`, `/search` while away from screen)
4. Vault content readback (`/speak daily-log` for proofreading by ear)
5. Meeting/interview prep (STAR stories, company research read aloud)
6. Long document review (ADRs, design specs)
7. Accessibility fallback (any Augur output as audio)

## VibeVoice Evaluation (Rejected)

Microsoft VibeVoice was evaluated and rejected for this iteration:

| Issue | Detail |
|-------|--------|
| macOS incompatible | CUDA-only, no Metal/MPS support — macOS has no NVIDIA GPUs since 2016 |
| Heavy requirements | 0.5B-1.5B param models, 2-8 GB VRAM, CUDA toolkit |
| Code removed | TTS implementation code removed Sept 2025 (responsible AI concerns) |
| Research-only | Explicitly warns against production use |

Can be revisited if/when Metal support is added.
