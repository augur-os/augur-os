# AI Client Cloud Execution Support - Design Spec

**Date:** 2026-04-24
**Status:** Proposed
**Scope:** Upgrade Augur's Codex, Claude, Gemini, and GitHub Copilot client support so each client has a first-class cloud execution path, while defaulting to read/review behavior and requiring explicit opt-in for mutation.

---

## Problem

Augur currently treats AI client support mostly as local client setup: generated instructions, skill exports, MCP configuration, plugin packages, and CLI detection. That is no longer enough for the main developer-client surface.

For many users, especially work-laptop users, the primary AI agent surface is increasingly cloud-backed:

- Codex can run hosted cloud tasks against GitHub repositories.
- Claude can run through GitHub Actions with Claude Code.
- Gemini can run through Gemini Code Assist on GitHub and Gemini CLI GitHub Actions.
- GitHub Copilot can run through Copilot cloud agent, Copilot CLI, repository skills, and GitHub-native issue/PR flows.

Augur has partial support today:

- Claude has `.github/workflows/claude.yml` with cloud-style GitHub Action triggers.
- Codex has `.github/workflows/codex.yml`, but it runs local Codex CLI on a runner and is not a full hosted Codex Cloud integration.
- Gemini has local plugin-pack support, but no first-class Augur cloud workflow/status surface.
- Copilot has shallow `.github/copilot-instructions.md` and memory support, but Copilot is disabled in `config/agents/ide_integrations.yaml`, missing from onboarding, and missing from plugin-pack.

If Copilot is expected to be the main agent for at least 50% of Augur users, Copilot cannot remain a shallow `.github` instructions adapter. More broadly, Augur needs a shared cloud execution model across all primary clients instead of one-off workflows.

---

## Goals

- Define a common cloud execution profile for Codex, Claude, Gemini, and Copilot.
- Default every client to read/review behavior.
- Require explicit opt-in for write, fix, commit, push, or PR creation modes.
- Add a durable status model that can explain why a cloud client is ready or blocked.
- Cover local client surfaces, cloud client surfaces, CLI loading, onboarding, plugin-pack/install, and skills sync.
- Keep work-laptop and enterprise constraints visible in the design instead of assuming admin permissions.
- Make Copilot a first-class target across sync, onboarding, plugin packaging, cloud readiness, and status reporting.

---

## Non-Goals

- Do not silently enable cloud mutation for any client.
- Do not require all users to connect hosted vendor agents.
- Do not store vendor secrets in the repository.
- Do not bypass GitHub organization policy, branch protection, enterprise permissions, or client security prompts.
- Do not remove existing local client support.
- Do not replace existing Claude and Codex workflows in the first implementation step unless they need normalization.
- Do not make dashboard code call local scripts directly. Dashboard status must flow through MCP tools and `POST /api/mcp/tool`.

---

## Decision

Adopt **Review-First Cloud Execution**.

Augur should support cloud execution for all four main clients, but the default cloud mode is read/review. Mutation modes are opt-in and client-specific.

The design introduces a shared **cloud execution profile**. A profile describes:

- client id
- local surfaces
- cloud surfaces
- generated repo files
- generated global files
- supported execution modes
- default mode
- mutation opt-in requirements
- required secrets
- required GitHub Apps or vendor setup
- supported trigger phrases
- onboarding checks
- enterprise blockers

This keeps client-specific details where they belong while giving onboarding, dashboard status, plugin-pack, and sync code one common contract.

---

## Execution Modes

Cloud execution should use a small shared mode vocabulary:

| Mode | Meaning | Default Allowed |
| --- | --- | --- |
| `read` | Answer questions using repo context without proposing a change | yes |
| `review` | Review a PR, summarize risks, comment findings | yes |
| `plan` | Produce an implementation plan without writing changes | yes |
| `fix` | Modify code in a branch or PR | opt-in |
| `commit` | Commit changes to a branch | opt-in |
| `pr` | Create or update a pull request | opt-in |

For user-facing commands, `read`, `review`, and `plan` are safe defaults. `fix`, `commit`, and `pr` require explicit enablement through profile config, onboarding, or repository policy.

---

## Cloud Profile Schema

Profiles should live in repo config rather than being hardcoded in individual adapters. A concrete file name can be chosen during implementation, but the schema should resemble:

```yaml
clients:
  codex:
    display_name: OpenAI Codex
    local:
      cli: codex
      config_paths:
        - ~/.codex/config.toml
      plugin_pack: codex
      mcp_client_id: codex
    cloud:
      vendor_surface: codex-cloud
      github_workflow: .github/workflows/codex.yml
      hosted: true
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@codex-ask"]
        review: ["@codex-review"]
        fix: ["@codex-fix"]
      requirements:
        - chatgpt_account
        - github_connector
      optional_secrets: []
      enterprise_notes:
        - "Codex cloud may require ChatGPT workspace admin setup."

  claude:
    display_name: Claude Code
    local:
      cli: claude
      config_paths:
        - ~/.claude/
      plugin_pack: cowork
      mcp_client_id: claude-code
    cloud:
      vendor_surface: claude-code-action
      github_workflow: .github/workflows/claude.yml
      hosted: false
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@claude-ask"]
        review: ["@claude-review"]
        fix: ["@claude-fix", "@claude-review-fix"]
      requirements:
        - github_actions
        - CLAUDE_CODE_OAUTH_TOKEN

  gemini:
    display_name: Gemini
    local:
      cli: gemini
      config_paths:
        - ~/.gemini/
      plugin_pack: gemini
      mcp_client_id: gemini
    cloud:
      vendor_surface: gemini-code-assist
      github_workflow: .github/workflows/gemini.yml
      hosted: mixed
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["/gemini"]
        review: ["/gemini review", "@gemini-cli /review"]
        fix: ["@gemini-cli /fix"]
      requirements:
        - gemini_code_assist_app_or_gemini_api_key
      enterprise_notes:
        - "Gemini Code Assist Enterprise setup may require Google Cloud IAM and Developer Connect."

  copilot:
    display_name: GitHub Copilot
    local:
      cli: copilot
      config_paths:
        - ~/.copilot/
        - .github/
      plugin_pack: copilot
      mcp_client_id: copilot
    cloud:
      vendor_surface: copilot-cloud-agent
      github_workflow: null
      hosted: true
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@copilot"]
        review: ["@copilot review"]
        fix: ["@copilot", "assign issue to Copilot"]
      requirements:
        - github_copilot_plan
        - copilot_cloud_agent_enabled
      enterprise_notes:
        - "Copilot cloud agent availability depends on GitHub plan, organization policy, and repository enablement."
```

This schema is intentionally descriptive. Implementation can split it into platform config, workflow templates, and onboarding metadata as long as the same contract is exposed through MCP.

---

## Client Matrix

| Client | Local Surface | Cloud Surface | Current Augur State | Target State |
| --- | --- | --- | --- | --- |
| Codex | `.codex`, Codex CLI, Codex plugin-pack, MCP | Codex Cloud, GitHub delegation, current CLI workflow | Strong local support; runner-local GitHub workflow exists | Normalize cloud status and distinguish hosted Codex Cloud from runner-local workflow |
| Claude | `.claude`, Claude Code, Cowork plugin-pack, MCP | Claude Code GitHub Action | Strongest existing cloud workflow | Add profile/status normalization and keep review-first default |
| Gemini | `.gemini`, Gemini CLI extension, MCP | Gemini Code Assist on GitHub, `run-gemini-cli` workflow | Local plugin-pack exists; cloud execution is not first-class | Add cloud workflow/status and Code Assist setup checks |
| Copilot | `.github`, Copilot CLI, VS Code, skills, MCP | Copilot cloud agent, issue/PR assignment, GitHub-native agent | Shallow generated instructions; disabled config; no onboarding/plugin-pack | First-class sync, onboarding, plugin-pack, cloud readiness, and status |

---

## Repository Outputs

Cloud-capable sync should be able to generate or validate these repo-local surfaces:

### Shared

- `.github/workflows/<client>.yml` where the client uses GitHub Actions.
- `.github/AI_CLIENTS.md` or equivalent generated status/help document if a user-facing summary is useful.
- Generated cloud setup docs for missing secrets, GitHub Apps, and enterprise blockers.
- A machine-readable cloud status artifact under an Augur-managed generated path, if needed for dashboard/Browse.

### Codex

- Preserve `.github/workflows/codex.yml`.
- Mark it as `runner-local` unless it delegates to hosted Codex Cloud.
- Add hosted Codex Cloud setup detection/status where possible.
- Keep `.codex` team config and plugin-pack support as local surfaces.

### Claude

- Preserve `.github/workflows/claude.yml`.
- Detect `CLAUDE_CODE_OAUTH_TOKEN` availability without printing secret values.
- Classify triggers into read/review/write modes.
- Keep Cowork/Claude local plugin-pack surfaces separate from GitHub Action status.

### Gemini

- Add or validate `.github/workflows/gemini.yml` for `google-github-actions/run-gemini-cli`.
- Support Gemini Code Assist on GitHub readiness checks:
  - GitHub App installed or not detectable.
  - consumer versus enterprise setup notes.
  - `.gemini/config.yaml` and `.gemini/styleguide.md` presence for review customization.
- Keep generated `.gemini/skills/` local-only and untracked according to current Augur policy.
- Keep the Gemini plugin-pack extension under `~/.gemini/extensions/augur/`.

### Copilot

- Generate correct Copilot repository assets:
  - `.github/copilot-instructions.md`
  - `.github/instructions/*.instructions.md`
  - `.github/prompts/*.prompt.md`
  - `.github/agents/*.agent.md` when needed
  - `.github/skills/<skill>/SKILL.md`
- Support Copilot CLI plugin packaging once the plugin-pack target exists.
- Support Copilot cloud agent readiness checks:
  - Copilot plan availability, where detectable.
  - repository suggested actor check for `copilot-swe-agent`, where GitHub API permissions allow.
  - organization/repository disabled state, where detectable.
- Avoid writing user-global Copilot files by default. Project-first remains the baseline.

---

## Plugin-Pack Changes

`plugin-pack` should grow from three targets to four primary targets:

| Target | Client |
| --- | --- |
| `cowork` | Claude Desktop/Cowork |
| `codex` | OpenAI Codex |
| `gemini` | Gemini CLI |
| `copilot` | GitHub Copilot |

Copilot packaging should not be a copy of Codex packaging. It should use Copilot-native conventions:

- repo skills in `.github/skills/<name>/SKILL.md`
- prompt files in `.github/prompts/*.prompt.md`
- instruction files in `.github/instructions/*.instructions.md`
- optional CLI plugin bundle if Copilot CLI plugin metadata requires a separate installable package

The first Copilot package should include the same high-value Augur surfaces as Codex and Gemini:

- ask/search/save second-brain operations
- selected user-facing skills
- MCP server declaration or setup guidance where the target supports it
- concise cloud-agent instructions explaining read/review-first behavior

---

## Skills Sync Changes

Skills sync needs to separate three kinds of output:

1. **Local discovery stubs**
   - Client-specific files that make local CLIs or IDEs discover Augur skills.

2. **Plugin/extension package output**
   - Codex, Gemini, Claude/Cowork, and Copilot installable bundles.

3. **Cloud execution assets**
   - GitHub workflows, cloud review config, cloud agent skills, prompts, and setup status.

Copilot should stop being treated as only a flat `.github/instructions` client. It needs cloud-aware outputs, including `.github/skills`.

Gemini should preserve the current policy: `.gemini/skills/` is local-only generated output, but cloud review config such as `.gemini/config.yaml` and `.gemini/styleguide.md` can be tracked when intentionally generated and reviewed.

---

## Onboarding Changes

`/onboard` should understand cloud execution as a first-class setup mode:

```text
/onboard --cloud
/onboard --cloud --client codex
/onboard --cloud --client claude
/onboard --cloud --client gemini
/onboard --cloud --client copilot
/onboard --cloud --mode review
/onboard --cloud --mode write
```

The default `/onboard --cloud` should run read-only checks and report a matrix:

| Status | Meaning |
| --- | --- |
| `ready` | Required local/cloud setup is present for the default read/review mode |
| `local-only` | Local client works, cloud execution is not configured |
| `missing-secret` | Workflow exists but required GitHub secret is missing or not detectable |
| `needs-github-app` | Vendor GitHub App or connector must be installed |
| `needs-enterprise-admin` | Organization or workspace admin action is required |
| `disabled-by-policy` | Client or cloud mode is disabled in Augur or org policy |
| `unsupported` | Client does not support the requested mode |
| `unknown` | Status cannot be detected with current permissions |

Onboarding should never ask for secret values in chat. It should print exact GitHub/CLI steps and verify after the user completes them.

---

## CLI Load and Runtime Checks

Cloud support should not assume local CLI support, and local CLI support should not imply cloud readiness.

Each client should report:

- local CLI present
- local CLI authenticated
- local MCP configured
- plugin/extension installed
- cloud review ready
- cloud mutation enabled
- cloud mutation blocked reason

Examples:

- Copilot CLI exists, but Copilot cloud agent disabled by org policy.
- Codex CLI exists, but hosted Codex Cloud GitHub connector is not configured.
- Claude workflow exists, but `CLAUDE_CODE_OAUTH_TOKEN` is missing.
- Gemini CLI exists, but Gemini Code Assist GitHub App is not installed.

---

## Dashboard and Browse Status

The dashboard should eventually expose the same status through MCP rather than direct filesystem or process calls.

Useful user-facing views:

- AI Clients overview: local, cloud review, cloud write columns.
- Per-client setup detail: what is installed, what is missing, what exact action is needed.
- Generated surface inventory: which repo/global files Augur owns for each client.
- Cloud execution safety: which modes are enabled and which are blocked.

No dashboard implementation is part of this design checkpoint, but the profile schema should be shaped so dashboard support is straightforward later.

---

## Safety Model

Read/review-first is mandatory for the default cloud rollout.

Mutation requires all of:

1. Client supports the requested mutation mode.
2. Augur profile enables the mutation mode.
3. Required secret or GitHub App setup is present.
4. Repository policy allows the operation.
5. User invokes a mutation trigger or command explicitly.

For generated workflows, mutation jobs should have narrower triggers than review jobs. For example, `@client-review` and `@client-fix` should be separate paths, not one ambiguous path that decides mutation from prompt wording alone.

---

## Implementation Slices

This spec should be implemented in bounded slices after approval:

1. **Profile and status foundation**
   - Add cloud execution profile config.
   - Add parser/validator tests.
   - Add MCP/status surface or local library used by onboarding.

2. **Onboarding and detection**
   - Add `/onboard --cloud` matrix.
   - Detect local CLI, plugin install, workflow, secrets where possible, GitHub App readiness where possible.

3. **Copilot first-class local support**
   - Enable Copilot in IDE/client config.
   - Add Copilot plugin-pack target.
   - Generate `.github/skills`, prompts, agents, and instructions.

4. **Cloud workflow normalization**
   - Normalize Claude/Codex workflow metadata.
   - Add Gemini cloud workflow support.
   - Add Copilot cloud agent setup/status docs and API checks.

5. **Dashboard/Browse visibility**
   - Surface cloud execution readiness and generated assets through MCP-backed dashboard views.

---

## Tests and Verification

Expected verification coverage:

- Unit tests for cloud profile parsing and validation.
- Unit tests for status classification.
- Tests that mutation modes are disabled unless explicitly enabled.
- Tests that Copilot generated files use `.github` native paths.
- Tests that Gemini `.gemini/skills/` remains ignored/local-only while intentional cloud review config can be tracked.
- Tests that onboarding reports missing secrets/apps without exposing secret values.
- Tests that existing Claude and Codex workflows still expose read/review triggers.
- Tests that plugin-pack supports `copilot` without regressing `cowork`, `codex`, or `gemini`.

Manual verification should include:

```bash
python skills/plugin-pack/scripts/plugin_assembler.py --target codex
python skills/plugin-pack/scripts/plugin_assembler.py --target gemini
python skills/plugin-pack/scripts/plugin_assembler.py --target copilot
python skills/onboard/... --cloud --status
```

Exact commands may change during implementation depending on the existing onboarding entrypoint.

---

## Open Questions

- Should Augur generate a tracked `.github/workflows/gemini.yml`, or offer it behind an explicit cloud install command?
- Should Copilot cloud agent setup use GitHub API checks directly, or only report human setup steps when permissions are insufficient?
- Should hosted Codex Cloud status be detected through OpenAI/Codex APIs, GitHub artifacts, or documented as an external setup prerequisite?
- Should cloud mutation enablement live in repo config, user config, or both?
- Should dashboard show cloud write disabled as a warning or as the normal safe default?

---

## Reference Sources

- GitHub Copilot cloud agent: `https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent`
- GitHub Copilot agent skills: `https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-skills`
- GitHub Copilot repository instructions: `https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions`
- OpenAI Codex Cloud: `https://developers.openai.com/codex/cloud`
- OpenAI Codex enterprise setup: `https://developers.openai.com/codex/enterprise/admin-setup`
- Claude Code GitHub Actions: `https://docs.anthropic.com/en/docs/claude-code/github-actions`
- Gemini Code Assist on GitHub: `https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github`
- Gemini Code Assist review behavior: `https://developers.google.com/gemini-code-assist/docs/review-repo-code`
- Gemini CLI GitHub Action: `https://github.com/google-github-actions/run-gemini-cli`
- Gemini Code Assist repository customization: `https://developers.google.com/gemini-code-assist/docs/customize-repo-review`
