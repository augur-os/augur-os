---
id: profile
label: Voice Profile
description: Run, update, or view the bilingual voice-profile personalization interview.
icon: UserRound
x-augur-export-command: false
---

# /profile

Manage the voice-profile personalization journey.

## Usage

```text
/profile interview
/profile update [en|he]
/profile view [en|he]
```

## Contract

- Ask the user to choose English (`en`) or Hebrew (`he`) at the start of `/profile interview`.
- Store interview progress in `vault/profile/<language>/interview-in-progress.yaml`.
- Call `vault-write` after every answer before asking the next question.
- Load `project-brain/capabilities/skills/knowledge/prompts/voice-profile/interview-<language>.md` as the interview prompt.
- Load `project-brain/capabilities/skills/knowledge/prompts/voice-profile/summary-<language>.md` for compression.
- When compression succeeds, call `profile-write` with `content`, `mode` (`full` or `update`), and `language`.
- Never overwrite one language's profile or in-progress state while working on the other language.

## Actions

### `/profile interview`

Ask: "Run the interview in English (en) or Hebrew (he)?" Re-ask once on invalid input; on a second invalid input, default to `en`.

If `vault/profile/<language>/interview-in-progress.yaml` exists, resume at the next unanswered question. If it is complete, ask whether to compress now into `vault/profile/<language>/about-me.md`.

If no state exists, start a new state file with:

```yaml
version: 1
language: en
total: 100
answered: 0
mode: full
qa_pairs: []
```

Run the interview inline in chat. After each answer, append the QA pair and persist the whole YAML state through `vault-write`. If `vault-write` fails, stop and report the failure.

### `/profile update [en|he]`

Update an existing language profile. If no language argument is provided, use the only existing profile or ask the user to choose when both exist. Abort if neither `vault/profile/en/about-me.md` nor `vault/profile/he/about-me.md` exists.

Ask 10-20 delta questions about what changed since the last interview. Persist progress in the same state file with `mode: update`, then merge-compress the existing profile plus new answers and call `profile-write`.

### `/profile view [en|he]`

Read and print the requested `about-me.md`. With no language argument, print the only existing profile or ask the user to choose when both exist.
