---
title: 'GitHub - open-gitagent/gitagent: A universal git-native AI agent framework.
  Your agent lives inside a git repo — identity, rules, memory, tools, and skills
  are all version-controlled files.'
x-augur-note-type: url
canonical_url: https://github.com/open-gitagent/gitagent
content_hash: sha256:c3d3d1fef1e81376cd6a127e20f819103abbe4e13de7332d6094e733b38c2cd1
tags: []
captured_at: '2026-05-31T21:00:21.213441Z'
_source_type: url
---

# GitHub - open-gitagent/gitagent: A universal git-native AI agent framework. Your agent lives inside a git repo — identity, rules, memory, tools, and skills are all version-controlled files.

> [!summary]
> A universal git-native multimodal always learning AI Agent (TinyHuman)
> Your agent lives inside a git repo — identity, rules, memory, tools, and skills are all version-controlled files.
> Install • Quick Start • SDK • Architecture • Tools • Hooks • Skills • Plugins
> Most agent frameworks treat configuration as code scattered across your application. Gitagent flips this — your agent IS a git repository:
> agent.yaml
> — model, tools, runtime configSOUL.md
> — personality and identityRULES.md
> — behavioral constraintsmemory/
> — git-committed memory with full historytools/
> — declarative YAML tool definitionsskills/
> — composable skill moduleshooks/
> — lifecycle hooks (script or programmatic)
> Fork an agent. Branch a personality. git log
> your agent's memory. Diff its rules. This is agents as repos.
> Copy, pas

## Source

- URL: https://github.com/open-gitagent/gitagent
- Captured: 2026-05-31T21:00:21.213441Z

## Body

A universal git-native multimodal always learning AI Agent (TinyHuman)
Your agent lives inside a git repo — identity, rules, memory, tools, and skills are all version-controlled files.
Install • Quick Start • SDK • Architecture • Tools • Hooks • Skills • Plugins
Most agent frameworks treat configuration as code scattered across your application. Gitagent flips this — your agent IS a git repository:
agent.yaml
— model, tools, runtime configSOUL.md
— personality and identityRULES.md
— behavioral constraintsmemory/
— git-committed memory with full historytools/
— declarative YAML tool definitionsskills/
— composable skill moduleshooks/
— lifecycle hooks (script or programmatic)
Fork an agent. Branch a personality. git log
your agent's memory. Diff its rules. This is agents as repos.
Copy, paste, run. That's it — no cloning, no manual setup. The installer handles everything:
bash <(curl -fsSL "https://raw.githubusercontent.com/open-gitagent/gitagent/main/install.sh?$(date +%s)")
This will:
- Install gitagent globally via npm
- Walk you through API key setup (Quick or Advanced mode)
- Launch the voice UI in your browser at
http://localhost:3333
Requirements: Node.js 18+, npm, git
npm install -g @open-gitagent/gitagent
Run your first agent in one line:
export OPENAI_API_KEY="sk-..."
gitagent --dir ~/my-project "Explain this project and suggest improvements"
That's it. Gitagent auto-scaffolds everything on first run — agent.yaml
, SOUL.md
, memory/
— and drops you into the agent.
Clone a GitHub repo, run an agent on it, auto-commit and push to a session branch:
gitagent --repo https://github.com/org/repo --pat ghp_xxx "Fix the login bug"
Resume an existing session:
gitagent --repo https://github.com/org/repo --pat ghp_xxx --session gitagent/session-a1b2c3d4 "Continue"
Token can come from env instead of --pat
:
export GITHUB_TOKEN=ghp_xxx
gitagent --repo https://github.com/org/repo "Add unit tests"
npm install gitagent
import { query } from "gitagent";
// Simple query
for await (const msg of query({
prompt: "List all TypeScript files and summarize them",
dir: "./my-agent",
model: "openai:gpt-4o-mini",
})) {
if (msg.type === "delta") process.stdout.write(msg.content);
if (msg.type === "assistant") console.log("\n\nDone.");
}
// Local repo mode via SDK
for await (const msg of query({
prompt: "Fix the login bug",
model: "openai:gpt-4o-mini",
repo: {
url: "https://github.com/org/repo",
token: process.env.GITHUB_TOKEN!,
},
})) {
if (msg.type === "delta") process.stdout.write(msg.content);
}
The SDK provides a programmatic interface to Gitagent agents. It mirrors the Claude Agent SDK pattern but runs in-process — no subprocesses, no IPC.
Returns an AsyncGenerator<GCMessage>
that streams agent events.
import { query } from "gitagent";
for await (const msg of query({
prompt: "Refactor the auth module",
dir: "/path/to/agent",
model: "anthropic:claude-sonnet-4-5-20250929",
})) {
switch (msg.type) {
case "delta": // streaming text chunk
process.stdout.write(msg.content);
break;
case "assistant": // complete response
console.log(`\nTokens: ${msg.usage?.totalTokens}`);
break;
case "tool_use": // tool invocation
console.log(`Tool: ${msg.toolName}(${JSON.stringify(msg.args)})`);
break;
case "tool_result": // tool output
console.log(`Result: ${msg.content}`);
break;
case "system": // lifecycle events & errors
console.log(`[${msg.subtype}] ${msg.content}`);
break;
}
}
Define custom tools the agent can call:
import { query, tool } from "gitagent";
const search = tool(
"search_docs",
"Search the documentation",
{
properties: {
query: { type: "string", description: "Search query" },
limit: { type: "number", description: "Max results" },
},
required: ["query"],
},
async (args) => {
const results = await mySearchEngine(args.query, args.limit ?? 10);
return { text: JSON.stringify(results), details: { count: results.length } };
},
);
for await (const msg of query({
prompt: "Find docs about authentication",
tools: [search],
})) {
// agent can now call search_docs
}
Programmatic lifecycle hooks for gating, logging, and control:
for await (const msg of query({
prompt: "Deploy the service",
hooks: {
preToolUse: async (ctx) => {
// Block dangerous operations
if (ctx.toolName === "cli" && ctx.args.command?.includes("rm -rf"))
return { action: "block", reason: "Destructive command blocked" };
// Modify arguments
if (ctx.toolName === "write" && !ctx.args.path.startsWith("/safe/"))
return { action: "modify", args: { ...ctx.args, path: `/safe/${ctx.args.path}` } };
return { action: "allow" };
},
onError: async (ctx) => {
console.error(`Agent error: ${ctx.error}`);
},
},
})) {
// ...
}
my-agent/
├── agent.yaml # Model, tools, runtime config
├── SOUL.md # Agent identity & personality
├── RULES.md # Behavioral rules & constraints
├── DUTIES.md # Role-specific responsibilities
├── memory/
│ └── MEMORY.md # Git-committed agent memory
├── tools/
│ └── *.yaml # Declarative tool definitions
├── skills/
│ └── <name>/
│ ├── SKILL.md # Skill instructions (YAML frontmatter)
│ └── scripts/ # Skill scripts
├── workflows/
│ └── *.yaml|*.md # Multi-step workflow definitions
├── agents/
│ └── <name>/ # Sub-agent definitions
├── plugins/
│ └── <name>/ # Local plugins (plugin.yaml + tools/hooks/skills)
├── hooks/
│ └── hooks.yaml # Lifecycle hook scripts
├── knowledge/
│ └── index.yaml # Knowledge base entries
├── config/
│ ├── default.yaml # Default environment config
│ └── <env>.yaml # Environment overrides
├── examples/
│ └── *.md # Few-shot examples
└── compliance/
└── *.yaml # Compliance & audit config
spec_version: "0.1.0"
name: my-agent
version: 1.0.0
description: An agent that does things
model:
preferred: "anthropic:claude-sonnet-4-5-20250929"
fallback: ["openai:gpt-4o"]
constraints:
temperature: 0.7
max_tokens: 4096
tools: [cli, read, write, memory]
runtime:
max_turns: 50
timeout: 120
# Optional
extends: "https://github.com/org/base-agent.git"
skills: [code-review, deploy]
delegation:
mode: auto
compliance:
risk_level: medium
human_in_the_loop: true
Define tools as YAML in tools/
:
# tools/search.yaml
name: search
description: Search the codebase
input_schema:
properties:
query:
type: string
description: Search query
path:
type: string
description: Directory to search
required: [query]
implementation:
script: search.sh
runtime: sh
The script receives args as JSON on stdin and returns output on stdout.
Script-based hooks in hooks/hooks.yaml
:
hooks:
on_session_start:
- script: validate-env.sh
description: Check environment is ready
pre_tool_use:
- script: audit-tools.sh
description: Log and gate tool usage
post_response:
- script: notify.sh
on_error:
- script: alert.sh
Hook scripts receive context as JSON on stdin and return:
{ "action": "allow" }
{ "action": "block", "reason": "Not permitted" }
{ "action": "modify", "args": { "modified": "args" } }
Skills are composable instruction modules in skills/<name>/
:
skills/
code-review/
SKILL.md
scripts/
lint.sh
---
name: code-review
description: Review code for quality and security
---
# Code Review
When reviewing code:
1. Check for security vulnerabilities
2. Verify error handling
3. Run the lint script for style checks
Invoke via CLI: /skill:code-review Review the auth module
Plugins are reusable extensions that can provide tools, hooks, skills, prompts, and memory layers. They follow the same git-native philosophy — a plugin is a directory with a plugin.yaml
manifest.
# Install from git URL
gitagent plugin install https://github.com/org/my-plugin.git
# Install from local path
gitagent plugin install ./path/to/plugin
# Install with options
gitagent plugin install <source> --name custom-name --force --no-enable
# List all discovered plugins
gitagent plugin list
# Enable / disable
gitagent plugin enable my-plugin
gitagent plugin disable my-plugin
# Remove
gitagent plugin remove my-plugin
# Scaffold a new plugin
gitagent plugin init my-plugin
id: my-plugin # Required, kebab-case
name: My Plugin
version: 0.1.0
description: What this plugin does
author: Your Name
license: MIT
engine: ">=0.3.0" # Min gitagent version
provides:
tools: true # Load tools from tools/*.yaml
skills: true # Load skills from skills/
prompt: prompt.md # Inject into system prompt
hooks:
pre_tool_use:
- script: hooks/audit.sh
description: Audit tool calls
config:
properties:
api_key:
type: string
description: API key
env: MY_API_KEY # Env var fallback
timeout:
type: number
default: 30
required: [api_key]
entry: index.ts # Optional programmatic entry point
plugins:
my-plugin:
enabled: true
source: https://github.com/org/my-plugin.git # Auto-install on load
version: main # Git branch/tag
config:
api_key: "${MY_API_KEY}" # Supports env interpolation
timeout: 60
Config resolution priority: agent.yaml config
> env var
> manifest default
.
Plugins are discovered in this order (first match wins):
- Local —
<agent-dir>/plugins/<name>/
- Global —
~/.gitagent/plugins/<name>/
- Installed —
<agent-dir>/.gitagent/plugins/<name>/
Plugins with an entry
field in their manifest get a full API:
// index.ts
import type { GitagentPluginApi } from "gitagent";
export async function register(api: GitagentPluginApi) {
// Register a tool
api.registerTool({
name: "search_docs",
description: "Search documentation",
inputSchema: {
properties: { query: { type: "string" } },
required: ["query"],
},
handler: async (args) => {
const results = await search(args.query);
return { text: JSON.stringify(results) };
},
});
// Register a lifecycle hook
api.registerHook("pre_tool_use", async (ctx) => {
api.logger.info(`Tool called: ${ctx.tool}`);
return { action: "allow" };
});
// Add to system prompt
api.addPrompt("Always check docs before answering questions.");
// Register a memory layer
api.registerMemoryLayer({
name: "docs-cache",
path: "memory/docs-cache.md",
description: "Cached documentation lookups",
});
}
Available API methods:
my-plugin/
├── plugin.yaml # Manifest (required)
├── tools/ # Declarative tool definitions
│ └── *.yaml
├── hooks/ # Hook scripts
├── skills/ # Skill modules
├── prompt.md # System prompt addition
└── index.ts # Programmatic entry point
Gitagent works with any LLM provider supported by pi-ai:
# agent.yaml
model:
preferred: "anthropic:claude-sonnet-4-5-20250929"
fallback:
- "openai:gpt-4o"
- "google:gemini-2.0-flash"
Supported providers: anthropic
, openai
, google
, xai
, groq
, mistral
, and more.
Agents can extend base agents:
# agent.yaml
extends: "https://github.com/org/base-agent.git"
# Dependencies
dependencies:
- name: shared-tools
source: "https://github.com/org/shared-tools.git"
version: main
mount: tools
# Sub-agents
delegation:
mode: auto
Built-in compliance validation and audit logging:
# agent.yaml
compliance:
risk_level: high
human_in_the_loop: true
data_classification: confidential
regulatory_frameworks: [SOC2, GDPR]
recordkeeping:
audit_logging: true
retention_days: 90
Audit logs are written to .gitagent/audit.jsonl
with full tool invocation traces.
Gitagent ships with built-in OpenTelemetry instrumentation. Set OTEL_EXPORTER_OTLP_ENDPOINT
and telemetry is on; leave it unset and runtime cost is zero.
Three layers of signals:
- HTTP-level —
@opentelemetry/instrumentation-undici
auto-patchesfetch
/undici
, so every LLM provider call (Anthropic, OpenAI, Google, …) gets a client span with URL, status code, and timing. gen_ai.chat
spans — emitted on every assistantmessage_end
. Carrygen_ai.system
,gen_ai.request.model
,gen_ai.usage.input_tokens
,gen_ai.usage.output_tokens
,gen_ai.response.finish_reasons
, andgitagent.cost_usd
. Span/metric content never contains the prompt or completion text.gitagent.tool.execute
spans — wrap every tool call withtool.name
,tool.call_id
,tool.status
(ok
/error
), andtool.error_message
on failure.
A root gitagent.agent.session
span opens at agent construction and closes on every exit path (success, hook-block, SIGINT, error).
Just set the endpoint — no --import
flag, no extra install steps:
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 gitagent -p "your prompt"
Telemetry is enabled automatically when the endpoint is set and disabled when it is not. To force-disable even when the endpoint is set, pass GITAGENT_OTEL_ENABLED=false
.
For programmatic embedders, call initTelemetry
explicitly — you control when initialisation happens:
import { initTelemetry, shutdownTelemetry, query } from "gitagent";
await initTelemetry({ serviceName: "my-app" });
for await (const msg of query({ prompt: "hello", model: "anthropic:claude-4-6-sonnet-latest" })) {
// …
}
await shutdownTelemetry();
OTEL_EXPORTER_OTLP_ENDPOINT
and OTEL_EXPORTER_OTLP_HEADERS
are read automatically by the OTLP exporter when not supplied programmatically. Pass exporterEndpoint
/ headers
only when you need to override env-based config in code.
Print spans directly to stdout — useful for local debugging:
OTEL_TRACES_EXPORTER=console gitagent -p "test"
docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 gitagent -p "test"
# Open http://localhost:16686 → service "gitagent"
Contributions are welcome! Please see CONTRIBUTING.md for guidelines.
What is Gitagent? GitAgent (formerly Gitclaw) is a git-native AI agent framework where the agent IS a git repository. Identity, rules, memory, tools, and skills are all version-controlled files, enabling "agents as repos" paradigm.
How does Gitagent differ from other agent frameworks? Unlike frameworks that scatter configuration across application code, Gitagent makes the agent itself a git repo:
- Fork an agent → inherit personality, rules, tools
- Branch → create alternate personality versions
git log
→ see agent's memory evolution- Diff → track rule changes over time
What is the "agents as repos" concept? Your agent lives in a git repository with structured files:
agent.yaml
— model, tools, runtime configSOUL.md
— personality and identityRULES.md
— behavioral constraintsmemory/
— git-committed memory with full historytools/
— declarative YAML tool definitionsskills/
— composable skill moduleshooks/
— lifecycle hooks
What are the requirements?
Node.js 18+ (or 20+ recommended), npm, and git. Install globally with npm install -g @open-gitagent/gitagent
.
How do I set up API keys? Run the installer for guided setup:
bash <(curl -fsSL "https://raw.githubusercontent.com/open-gitagent/gitagent/main/install.sh")
Or set manually:
export OPENAI_API_KEY="sk-..."
Which LLM providers are supported?
- OpenAI (GPT-4o, GPT-4o-mini, etc.)
- Anthropic (Claude models via native SDK)
- Any OpenAI-compatible provider
Use --model
flag to override: gitagent --model anthropic:claude-sonnet-4-5-20250929
What is the SDK and how do I use it?
The SDK provides programmatic access via query()
function that streams agent events:
import { query } from "gitagent";
for await (const msg of query({ prompt: "hello", model: "openai:gpt-4o-mini" })) {
if (msg.type === "delta") process.stdout.write(msg.content);
}
How do local repo mode sessions work? Clone a GitHub repo, run an agent on it, auto-commit to a session branch:
gitagent --repo https://github.com/org/repo --pat ghp_xxx "Fix the bug"
Resume with: gitagent --repo URL --session gitagent/session-xxx "Continue"
What hooks are available?
Hooks are lifecycle scripts or programmatic handlers in hooks/
directory. They trigger on agent events like tool execution, session start/end, or memory updates.
How do I create custom tools?
Define tools in tools/
directory using declarative YAML format. Each tool specifies name, description, parameters, and execution logic.
How do I add skills?
Create skill modules in skills/
directory. Skills are composable and can be imported from installed packages or defined locally.
What telemetry options are available? OpenTelemetry integration for observability:
- Set
OTEL_EXPORTER_OTLP_ENDPOINT
for auto-enable - Use
OTEL_TRACES_EXPORTER=console
for local debugging - Jaeger quickstart with Docker
Why is my agent not responding?
- Check API key is set (
OPENAI_API_KEY
or equivalent) - Verify network connectivity to LLM provider
- Use
--verbose
flag for detailed logs - Check
agent.yaml
model configuration
How do I debug agent behavior?
- Use console exporter:
OTEL_TRACES_EXPORTER=console gitagent -p "test"
- Check spans in Jaeger:
docker run -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one
- Inspect
memory/
directory for agent state
Where can I get help?
- GitHub Issues: https://github.com/open-gitagent/gitagent/issues
- Examples: See README SDK section and CLI options
- Contributing: See CONTRIBUTING.md for guidelines
This project is licensed under the MIT License.
