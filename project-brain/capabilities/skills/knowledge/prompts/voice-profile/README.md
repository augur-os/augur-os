# Voice Profile — Almaya 2-step prompts

This directory ships the verbatim Almaya voice-profile prompts in English and Hebrew, used by `/profile interview` and the compression step that produces `vault/profile/<lang>/about-me.md`.

## Files

| File | Step | Language |
|---|---|---|
| `interview-en.md` | 1 — interviewer with 100 questions | English |
| `summary-en.md` | 2 — Voice Compiler producing `about-me.md` | English |
| `interview-he.md` | 1 — interviewer with 100 questions | Hebrew |
| `summary-he.md` | 2 — Voice Compiler producing `about-me.md` | Hebrew |

Each file contains the prompt content verbatim. No frontmatter — when the agent reads the file, the entire content is the prompt the agent must follow.

## Source and attribution

Author: Roey Parel — Almaya (almaya.ai).
Source: <https://almaya.ai/blog/creating-ai-voice-profile> (published publicly).

Both English and Hebrew versions are published side-by-side at the source URL.

## Usage

`project-brain/capabilities/skills/knowledge/commands/profile.md` (the `/profile` slash command) instructs the AI client to read the appropriate `interview-<lang>.md` at the start of an interview session, and `summary-<lang>.md` at the compression step.

The agent picks the language at the start of `/profile interview` and the state file `vault/profile/<lang>/interview-in-progress.yaml` records it for resume.

## Updating the prompts

If Almaya publishes a revised prompt, replace the file content verbatim and commit with a note linking the source revision. Do not paraphrase or partially-edit — these prompts are an external dependency and should track the source faithfully.
