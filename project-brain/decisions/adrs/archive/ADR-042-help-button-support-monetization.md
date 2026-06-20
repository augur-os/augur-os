---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Team
related: []
hub: null
tags:
- help
- button
- context
- support
- monetization
superseded_by: null
---

# ADR-042: Help Button — In-Context Support & Monetization Channel

## Context

Users building and operating their Augur dashboard will inevitably encounter issues — broken pages, missing data, misconfigured skills, or general confusion about how a feature works. Today the only support path is:

1. Open a GitHub issue (requires context-switching, manual log gathering)
2. A Qualtrics survey linked from Claude Code (generic, no Augur context)
3. Self-debugging (requires developer skills)

None of these capture **page context** (which hub, which skill, which errors are in the console). None offer a structured path from "I need help" to "here's a solution." And none generate revenue.

Meanwhile, Augur is open-source and privacy-first (ADR-006). Any monetization must respect these principles — no telemetry without consent, no lock-in, no paywalls on core features.

### The Opportunity

A **Help button** placed in the chat window (next to the existing Data and MCP Tools buttons) can:
- Capture rich, contextual support requests (page, skill, logs, errors)
- Route them to a central support server for triage
- Deliver fixes back via GitHub-native mechanisms (tags, patches)
- Offer monetization at the **resolution** point, not the request point
- Keep the core product fully open-source and functional without payment

## Decision

### 1. Help Button Placement & UI

Add a **Help** button to the FloatingChat toolbar (in `src/dashboard/components/FloatingChat.tsx`), alongside the existing Data and MCP Tools buttons.

```
┌─────────────────────────────────────────────────┐
│  [MCP Tools]  [Data]  [Help]          ⌨️ Input  │
└─────────────────────────────────────────────────┘
```

- **Icon**: `HelpCircle` (lucide-react)
- **Label**: "Help"
- **Visibility**: Always visible (both Dev and Operation modes)

### 2. Help Questionnaire Flow

When the user clicks Help, a modal opens with a structured questionnaire:

**Step 1 — Topic Selection** (auto-populated from page context):
```
What do you need help with?
○ This page has an error
○ A feature isn't working as expected
○ I don't understand how to use this
○ I want to request a feature
○ Something else: [free text]
```

**Step 2 — Context Gathering** (pre-filled, editable):
```
Page:        /control/logs        (auto-detected)
Skill:       daemon               (auto-detected from route)
Mode:        Dev                  (auto-detected)
Browser:     Chrome 120           (auto-detected, anonymized)
Description: [user fills in]
```

**Step 3 — Log Attachment** (opt-in):
```
☐ Attach browser console errors (last 50 entries)
☐ Attach relevant runtime logs (last 100 lines)
☐ Attach current page screenshot

[Preview what will be sent →]
```

**Step 4 — Privacy Confirmation**:
```
The following will be sent to Augur Support:
- Topic: "This page has an error"
- Page context: /control/logs (daemon skill)
- Console errors: 3 entries (click to preview)
- Runtime logs: 47 lines (click to preview)

⚠️ No personal data, API keys, or file contents are included.
   All data is stripped of PII before transmission.

[Send Report]  [Cancel]
```

### 3. Data Flow Architecture

```
┌──────────────┐     HTTPS POST      ┌──────────────────┐
│  Dashboard   │ ──────────────────→  │  Augur Support   │
│  Help Button │   (encrypted JSON)   │  Server (API)    │
└──────────────┘                      └────────┬─────────┘
                                               │
                                    ┌──────────▼─────────┐
                                    │  Triage Queue       │
                                    │  (GitHub Issues or  │
                                    │   internal DB)      │
                                    └──────────┬─────────┘
                                               │
                                    ┌──────────▼─────────┐
                                    │  Resolution         │
                                    │  (patch / tag /     │
                                    │   documentation)    │
                                    └──────────┬─────────┘
                                               │
                       ┌───────────────────────▼───────────────────────┐
                       │          Notification to User                  │
                       │  (channels skill: email + dashboard badge)     │
                       └───────────────────────────────────────────────┘
```

### 4. Support Server (External)

A lightweight API server (separate repository) that:
- Receives encrypted help requests
- Strips any remaining PII via automated sanitizer
- Creates triage entries (can be backed by GitHub Issues on a private repo)
- Tracks request → resolution lifecycle
- Sends resolution notifications back to the user's Augur instance

**Privacy Design**:
- User is identified by a **random support token** (generated locally, stored in `data/core/settings.yaml`)
- No email, IP, or personal data is required to submit
- Email is optional — only needed if user wants email notifications
- All communication is encrypted in transit (HTTPS)
- Support token can be rotated/deleted by user at any time

### 5. Resolution Delivery — GitHub-Native Patch Mechanism

Fixes are delivered as **tagged GitHub releases** with patch files:

```
GitHub Release: v1.2.3-fix-daemon-logs
├── CHANGELOG.md (human-readable description)
├── patches/
│   ├── 001-fix-log-rotation.patch     (git format-patch output)
│   └── 002-update-daemon-config.patch
└── metadata.json
    {
      "support_ticket": "AUGUR-1234",
      "affected_skills": ["daemon"],
      "affected_files": ["plugins/observability/skills/daemon/scripts/log_monitor.py"],
      "min_version": "1.0.0",
      "risk": "low",
      "tested": true
    }
```

**How users receive fixes**:

```
channels skill (polling loop, every 15 min):
  1. GET /api/v1/updates?token={support_token}&version={current_version}
  2. If updates available:
     a. Create review via channels registry:
        raise_review(
          title="Fix available: Dashboard log rotation",
          description="Patch for issue AUGUR-1234",
          actions=[
            { type: "LINK", label: "View Details", url: "..." },
            { type: "CHAIN", label: "Apply Patch", chain: "apply-patch", params: {...} },
            { type: "LINK", label: "Dismiss", url: None }
          ]
        )
     b. Send notification via configured channel (macOS notification, Telegram, etc.)
     c. If user provided email → send email notification too
```

**Patch application** (via `apply-patch` chain):
```bash
# Automated, but requires user approval via review system
git fetch origin
git stash  # preserve user changes
git apply patches/001-fix-log-rotation.patch --check  # dry run first
git apply patches/001-fix-log-rotation.patch
git stash pop  # restore user changes
npm run build  # rebuild if dashboard changes
```

### 6. Monetization — Resolution Page

The key insight: **monetization happens at the solution, not the request**. The help request is always free. When a resolution is ready, the user is presented with options:

**In-Dashboard Notification** (via channels skill review):
```
┌─────────────────────────────────────────────┐
│  ✅ Solution available for: "Log rotation    │
│     not working on daemon skill"             │
│                                              │
│  [View Solution →]                           │
└─────────────────────────────────────────────┘
```

**"View Solution" opens external resolution page** (hosted on augur support site):

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Solution: Fix Log Rotation in Daemon Skill         │
│  ──────────────────────────────────────────          │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  🆓 Free Patch                               │    │
│  │  Auto-apply this specific fix via your       │    │
│  │  dashboard. Open-source patch, MIT licensed. │    │
│  │  [Apply Patch]                               │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  📚 Builder Course                           │    │
│  │  Learn to debug & extend Augur yourself.     │    │
│  │  Covers: skill development, daemon config,   │    │
│  │  dashboard customization.                    │    │
│  │  [$49 — Self-Paced Course]                   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  🛠️ Expert Help                              │    │
│  │  1:1 session with an Augur expert.           │    │
│  │  Get this fixed + learn how to prevent it.   │    │
│  │  [$99/hour — Book Session]                   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  🤝 Partner Tools                            │    │
│  │  Recommended AI providers & tools that       │    │
│  │  integrate with Augur.                       │    │
│  │  [Browse Partners →]  (affiliate/referral)   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌───────────────────────────────────────────────────┐
│  │  🎓 Augur AI Builder Certification                │
│  │  Get certified. Build skills, chains, extensions.  │
│  │  Earn money helping others build theirs.           │
│  │  Perks: Builder Directory listing, paid tickets,   │
│  │  private community, early access, digital badge.   │
│  │  [$99 — Exam + Certificate]                        │
│  └───────────────────────────────────────────────────┘
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Revenue Streams**:

| Stream | Model | Privacy Impact |
|--------|-------|----------------|
| Free Patch | Free (goodwill, adoption) | None — git patches are open-source |
| Builder Course | One-time purchase | Email required for course access |
| Expert Help | Hourly rate | Scheduling requires contact info |
| Partner Tools | Affiliate/referral fees | User clicks tracked with consent |
| Builder Certification | One-time $99 | Email + profile required for directory listing |

**Critical Rule**: The free patch is **always available**. Paid options are upsells, not gates. The core fix is never behind a paywall.

### 7. Notification Flow (Channels Skill Integration)

The `channels` skill handles all notification delivery:

```python
# In channels skill — new support_checker module
class SupportNotificationChecker:
    """Polls support server for resolution updates."""

    def check_updates(self):
        token = self.get_support_token()
        if not token:
            return  # User hasn't submitted any help requests

        response = requests.get(
            f"{SUPPORT_API}/v1/updates",
            params={"token": token, "version": get_augur_version()},
            timeout=10
        )

        for update in response.json().get("updates", []):
            self.create_review(update)
            self.send_notification(update)

    def create_review(self, update):
        raise_review(
            title=f"Solution available: {update['title']}",
            description=update["summary"],
            category="support",
            urgency="normal",
            actions=[
                {"type": "LINK", "label": "View Solution",
                 "url": update["resolution_url"]},
                {"type": "CHAIN", "label": "Apply Patch",
                 "chain": "apply-support-patch",
                 "params": {"patch_url": update["patch_url"]}},
            ]
        )

    def send_notification(self, update):
        send_notification(
            message=f"Help request resolved: {update['title']}",
            channel="default",  # Uses user's preferred channel
            category="support"
        )
```

### 8. Negotiation / Follow-Up Flow

Users can interact with support through a lightweight comment thread:

```
Dashboard Review Card:
┌──────────────────────────────────────────────┐
│  🔔 Your help request: "Log rotation issue"  │
│  Status: In Progress                         │
│                                              │
│  Latest update: "We've identified the root   │
│  cause. A patch is being prepared."          │
│                                              │
│  [Reply]  [View Thread]  [Close Request]     │
└──────────────────────────────────────────────┘
```

- **Reply**: Sends a text message back to the support server (via API)
- **View Thread**: Opens the full conversation history
- **Close Request**: Marks the request as resolved

All communication flows through the same encrypted API. No email threads, no external accounts required.

### 9. Security — Patch Verification

Patches delivered via the support system must be verified:

```python
# In apply-support-patch chain
def apply_patch(patch_url: str, metadata: dict):
    # 1. Download patch file
    patch = download(patch_url)

    # 2. Verify patch signature (GPG-signed by Augur maintainers)
    if not verify_gpg_signature(patch, AUGUR_PUBLIC_KEY):
        raise SecurityError("Patch signature verification failed")

    # 3. Verify patch only touches declared files
    affected_files = parse_patch_files(patch)
    declared_files = set(metadata["affected_files"])
    if not affected_files.issubset(declared_files):
        raise SecurityError(
            f"Patch modifies undeclared files: {affected_files - declared_files}"
        )

    # 4. Dry run
    result = git_apply(patch, check=True)
    if not result.success:
        raise PatchError(f"Patch does not apply cleanly: {result.stderr}")

    # 5. Apply with user confirmation (via review system)
    raise_review(
        title="Confirm patch application",
        description=f"Apply {len(affected_files)} file changes?",
        actions=[
            {"type": "CHAIN", "label": "Apply", "chain": "git-apply-confirmed"},
            {"type": "LINK", "label": "View Diff", "url": patch_diff_url},
            {"type": "LINK", "label": "Cancel", "url": None},
        ]
    )
```

**Security Guarantees**:
- GPG signature verification (Augur maintainer keys)
- Declared file manifest — patch cannot modify files outside its declared scope
- Dry run before application
- User approval required before any code changes
- Git stash/restore to protect user work
- Full rollback capability (`git apply --reverse`)

## Architecture

```
src/dashboard/
├── components/
│   ├── FloatingChat.tsx          # MODIFIED: Add Help button
│   └── HelpModal.tsx             # NEW: Questionnaire modal
├── app/api/help/
│   └── route.ts                  # NEW: Proxy to support server
└── lib/
    └── help/
        ├── context-collector.ts  # NEW: Gather page/skill/error context
        └── pii-stripper.ts       # NEW: Remove sensitive data before send

plugins/admin/skills/channels/
├── lib/
│   └── support_checker.py        # NEW: Poll support server for updates
└── scripts/
    └── apply_support_patch.py    # NEW: Verify & apply patches

data/core/
├── settings.yaml                 # MODIFIED: Add support_token field
└── executor/chains/
    └── apply-support-patch.yaml  # NEW: Patch application chain
```

## Consequences

### Positive

- Users get structured, context-rich support without leaving the dashboard
- Support requests include relevant logs and errors automatically
- Fixes are delivered via standard git mechanisms (patches, tags)
- Monetization is ethical — free patch always available, paid options are value-adds
- Privacy-first — random token identification, opt-in logs, PII stripping
- Channels skill integration means notifications work across all user-configured channels
- GPG-signed patches prevent supply chain attacks
- Open-source integrity maintained — all patches are MIT-licensed

### Negative

- Requires standing up an external support server (new infrastructure)
- Channels skill gains polling responsibility (additional network requests)
- GPG key management adds operational complexity
- Resolution page is external — user leaves the dashboard briefly
- Monetization revenue depends on support volume and conversion

### Neutral

- Existing feedback API (`/api/prompts/feedback/`) remains unchanged (different purpose)
- Help button does not replace GitHub Issues (they serve different audiences)
- Patch mechanism is additive — users can still manually apply fixes via git

## Alternatives Considered

### Alternative 1: In-App Chat with Live Support

**Rejected**: Requires real-time support staffing, expensive at low scale, conflicts with privacy-first approach (live chat services typically require user accounts and tracking).

### Alternative 2: AI-Powered Auto-Resolution

**Rejected as primary**: Would require sending code/config to external AI services, violating privacy principles. However, the Builder Course could include AI-assisted debugging guides that run locally.

### Alternative 3: GitHub Issues Only

**Rejected as sole channel**: GitHub Issues lack page context, require a GitHub account, and don't support the monetization resolution page. However, the support server can create GitHub Issues internally for tracking.

### Alternative 4: Paywall on Patch Delivery

**Rejected**: Gating fixes behind payment would undermine open-source trust and violate the principle that core functionality is always free. Monetization must be at the value-add layer (education, expert help, partner tools), not the fix itself.

### Alternative 5: Community Forum for Support

**Considered as complement**: A community forum (Discourse, GitHub Discussions) could supplement the help system for peer-to-peer support. Not rejected — can be added later as the user base grows. The help button would remain the primary structured channel.

## Implementation Plan

1. **Phase 1 — Help Button UI**: Add button to FloatingChat, build questionnaire modal, implement context collector and PII stripper
2. **Phase 2 — Local Storage**: Store help requests locally first (no server), display in channels review queue
3. **Phase 3 — Support Server MVP**: Stand up API, receive requests, manual triage
4. **Phase 4 — Patch Delivery**: GPG signing, patch verification, apply-patch chain
5. **Phase 5 — Channels Integration**: Support checker polling, notification delivery, reply thread
6. **Phase 6 — Monetization Page**: Resolution page with free patch + paid options
7. **Phase 7 — Email Notifications**: Optional email for users who want it

## Open Questions

1. **Support server hosting**: Self-hosted vs managed? (Vercel API routes, Railway, or dedicated VPS)
2. **GPG key rotation**: How often? How to distribute updated public keys to Augur instances?
3. **Rate limiting**: How to prevent abuse of the support API without requiring authentication?
4. **Course platform**: Build custom or use existing (Teachable, Gumroad, etc.)?
5. **Partner program structure**: Affiliate vs referral vs sponsorship model?

## References

- ADR-006: Local-First Architecture
- ADR-034: CLI Chat Window with File Attachment
- ADR-035: CLI Chat Enhancements
- ADR-036: Chat Action Bar Partition
- ADR-041: Daemon Production Monitoring
- `src/dashboard/components/FloatingChat.tsx` (Help button placement)
- `plugins/admin/skills/channels/lib/registry.py` (notification SDK)
- `plugins/admin/skills/channels/SKILL.md` (channels skill)
