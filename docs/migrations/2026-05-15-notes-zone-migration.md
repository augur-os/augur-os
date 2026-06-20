# Notes-zone migration (ADR-751)

Date: 2026-05-16
Vault: C:\Users\intel\Projects\Au-vault
Dry run: moved=6 already_migrated=0 collisions=0 errors=0
Apply: moved=6 already_migrated=0 collisions=0 errors=0

Spot check: C:\Users\intel\Projects\Au-vault\notes\voice-profile-almaya.md contains `x-augur-note-type: prompt`.

Old folders (`inbox/`, `sources/`, `prompts/`) are retained as empty placeholders for one minor-version grace period.

## Browser verification (2026-05-16)

- Browser: Playwright Chromium, 1440x1000, localhost:3000.
- ViewModes tested: `notes` canonical plus `inbox`, `sources`, and `prompts` retired redirects.
- Redirects observed: `inbox -> /browse?view=notes`, `sources -> /browse?view=notes&type=url,file`, `prompts -> /browse?view=notes&type=prompt`.
- Cards rendered from real vault data: 5 URL/file-filtered notes and 1 prompt-filtered note.
- Detail panel verified: first URL note showed note type plus URL/domain detail rows.
- Client state: no chunk-load or hydration errors, no fatal toast, no blocking setup flyout.

## Real-data `/note` verification (2026-05-16)

- Plan URL precheck: `https://www.lesswrong.com/posts/J78QF6yvvKDsRBsK4/the-best-textbooks-on-every-subject` returned `HTTP 404`, so the successful URL capture used a reachable real URL.
- `/note <real URL>`: `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-url-www-gutenberg-org-files-1342-1342-h-1342-h-htm.md`
  - Frontmatter: `x-augur-note-type: url`, `canonical_url: https://www.gutenberg.org/files/1342/1342-h/1342-h.htm`
- `/note "<thought>"`: `C:\Users\intel\Projects\Au-vault\notes\2026-05-15-thought-adr-751-verification.md`
  - Frontmatter: `x-augur-note-type: thought`
- `/note --as prompt`: `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-prompt-adr-751-pr-review-verification.md`
  - Frontmatter: `x-augur-note-type: prompt`, `x-augur-prompt-triggerable: true`; body preserved `{{diff}}`.
- `/note <local PDF>`: `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-second-brain-intelligence-report.md`
  - Frontmatter: `x-augur-note-type: file`, `original_path: C:\Users\intel\Projects\Au-docs\brain\artifacts\second-brain-report-2026-05-12.pdf`; body includes extracted text from the PDF.
- `/ingest <url>` alias: printed `/ingest is deprecated; use /note instead. They take identical arguments.`, then wrote `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-url-example-com-something.md`
  - Frontmatter: `x-augur-note-type: url`, `canonical_url: https://example.com/something`

## Real-data audio verification (ADR-752, 2026-05-16)

- Voice memo source: `C:\Users\intel\Downloads\voice-memo-verify.m4a`, duration `66.32s`, provider `whisper-cpp 1.4.1`, classifier `voice-memo` confidence `0.91` via LLM-assisted callback. On Windows, this `.m4a` was exported from the same real local voice recording used for the first verification because macOS Voice Memos.app is unavailable on this host.
  - Note: `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-voice-adr-752-voice-memo-verification.md`
  - Frontmatter: `x-augur-note-type: voice-memo`, `audio_path: C:\Users\intel\Downloads\voice-memo-verify.m4a`, `transcript_status: complete`, `content_hash: 5a5e5083ed57b1e5`
- Meeting source: `C:\Users\intel\Downloads\meeting-verify.mp3`, public ELT Podcast conversation, duration `162.0s`, provider `whisper-cpp 1.4.1`, classifier `meeting` confidence `0.95` (`dialogue_questions=11`).
  - Note: `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-meeting-adr-752-meeting-verification.md`
  - Frontmatter: `x-augur-note-type: meeting`, `audio_path: C:\Users\intel\Downloads\meeting-verify.mp3`, `transcript_status: complete`, `attendee_count: 2`
  - Attendee note: transcript has named speakers in prose but no bracket-tagged speaker turns, so ADR-738 attendee slug resolution produced `0` matched slugs. The meeting writer now records an inferred attendee count of `2` from the real dialogue-question structure while keeping `attendee_slugs` absent unless person entities are resolved.
- Override checks:
  - `--memo` on the meeting audio wrote `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-voice-adr-752-meeting-override-as-memo.md` with confidence `1.0`.
  - `--meeting` on the voice audio wrote `C:\Users\intel\Projects\Au-vault\notes\2026-05-16-meeting-adr-752-voice-override-as-meeting.md` with confidence `1.0`.
- Browser verification: Playwright Chromium opened `http://localhost:3002/browse?view=notes&type=voice-memo,meeting`.
  - Voice and meeting cards rendered from the real vault index.
  - Detail panels rendered audio controls, transcript pane, provider metadata, attendee count for the meeting, and inert `Merge to timeline`.
  - `/api/vault-asset` returned byte-range media responses during the browser run: meeting MP3 `206 audio/mpeg`, original voice MP4 `206 video/mp4`. Post-gap fix, `C:\Users\intel\Downloads\voice-memo-verify.m4a` was verified with `ffprobe` as AAC audio, duration `66.57s`.
  - Screenshots: `C:\Users\intel\AppData\Local\Temp\adr752-browse-voice-detail.png`, `C:\Users\intel\AppData\Local\Temp\adr752-browse-meeting-detail.png`.
