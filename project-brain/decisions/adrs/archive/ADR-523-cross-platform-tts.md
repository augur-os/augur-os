---
status: Implemented
date: 2026-03-29
deciders:
  - Gur Sannikov
related: []
hub: command
tags: [tts, audio, accessibility]
superseded_by: null
---

# ADR-523: Cross-Platform Text-to-Speech

## Context

Augur had no way to speak content aloud. macOS has the built-in `say` command, but Windows has no simple equivalent. Users wanted to hear dashboard content, agent responses, and notifications without looking at the screen — for hands-free workflows, accessibility, and proofreading by ear.

Microsoft VibeVoice was evaluated as a high-quality alternative but rejected: CUDA-only (no macOS support since Apple dropped NVIDIA in 2016), 0.5-1.5B param models requiring dedicated GPU, TTS source code removed in Sept 2025 due to responsible AI concerns, and explicitly labeled research-only.

## Decision

Use OS-native TTS engines exclusively, exposed as a single MCP tool and a reusable dashboard component.

### TTS Engine (`skills/tts/scripts/tts_engine.py`)

- **macOS**: `subprocess.Popen(["say", text])` — zero dependencies
- **Windows**: `pyttsx3` wrapping SAPI/OneCore — single pip dependency
- **Interrupt**: every `speak()` call kills current speech first (`killall say` on macOS, `engine.stop()` on Windows)
- **No configuration**: OS default voice, rate, volume
- **Unsupported platforms**: returns error (Linux `espeak` deferred)

### MCP Tool (`skills/tts/scripts/mcp/`)

- Tool name: `speak`
- Parameters: `text: str`, `stop: bool = False`
- Response: `{"status": "speaking"|"stopped"|"error", "platform": "macos"|"windows", "length": int}`
- Registered via plugin auto-discovery (`register_tools()` pattern)

### Dashboard Component (`apps/dashboard/components/blocks/ReadAloudButton.tsx`)

- Reusable button with idle (Volume2 icon) and speaking (VolumeX icon) states
- Calls `useMcpMutation("speak")` — no skill code imports
- Wired into BlockRenderer: blocks with `readAloud: true` in manifest show button on hover
- Lives in framework layer since it only references MCP tool by name

### Skill Structure

```
skills/tts/
├── SKILL.md              # x-augur-hub: command, x-augur-type: service
├── scripts/
│   ├── tts_engine.py     # cross-platform TTS wrapper
│   └── mcp/              # MCP tool registration (3 files)
├── commands/
│   └── speak.md          # /speak slash command
├── augur/tests/           # 11 tests (7 engine + 4 MCP)
└── assets/seeds/
```

## Consequences

### Positive

- Zero-setup TTS on macOS (built-in `say`)
- Single pip dependency on Windows (`pyttsx3`)
- Sub-50ms latency — OS-native engines start near-instantly
- Any block can opt-in via `readAloud: true` manifest flag
- Skills/agents can call `speak` programmatically for notifications and responses

### Negative

- No voice cloning, emotion control, or multi-speaker support
- Windows quality depends on installed OneCore voices (decent on Win 10+, basic on older)
- Linux not supported (returns error)

### Neutral

- OS default voice only — users who want different voices must change OS settings
- Speech duration estimated at ~80ms/char for UI state — approximate, not tracked

## Alternatives Considered

### Alternative 1: VibeVoice (Microsoft)

Frontier voice AI with excellent quality (1.5B param TTS, 0.5B realtime). Rejected because: CUDA-only (no macOS), 2-8 GB VRAM required, source code removed, research-only.

### Alternative 2: Cloud TTS APIs (Google, AWS, Azure)

High quality, multi-language. Rejected because: requires API keys, network latency, cost per request, privacy concerns (sending text to cloud), violates local-first principle.

### Alternative 3: Tiered (OS-native default + VibeVoice opt-in)

Best of both worlds. Rejected because: VibeVoice only works on Windows with NVIDIA GPU — macOS users get no premium option, fragmenting the experience.

## References

- Design spec: `docs/superpowers/specs/2026-03-29-cross-platform-tts-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-29-cross-platform-tts.md`
- VibeVoice evaluation: https://github.com/microsoft/VibeVoice
