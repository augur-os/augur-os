## Detect Platform

Determine which AI agent/IDE you are running in:

| Check | Platform |
|-------|----------|
| You are Claude Code or `~/.claude/` exists | claude-code |
| You are Codex or `~/.codex/` exists | codex |
| You are Gemini CLI or `~/.gemini/` exists | gemini |
| `copilot --version` succeeds or `~/.copilot/` exists | copilot |
| GitHub suggested actors include `copilot-swe-agent` | copilot cloud agent ready |
| `~/.cursor/` or `~/Library/Application Support/Cursor/` exists | cursor |
| `~/.codeium/windsurf/` exists | windsurf |
| `~/.opencode/` exists | opencode |
| `~/Library/Application Support/Cline/` exists | cline |
| You are running inside VS Code | vscode |
| You are running inside Antigravity | antigravity |

If multiple match, prefer the one you are actually running inside.
If none match, ask the user.
