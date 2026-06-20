---
description: Manage human-readable RAG indexes across standard plugins. Provides search, status, reindex, cleanup, and purge. Usage: /rag [action] [skill_path] [query]
---
# /rag Command Execution

1. Command format is `/rag <action> <skill> [query]`
2. Actions available:
   - `search`: Queries for a concept in a given skill (`/rag search ai/skills/rag "how is evaluation done?"`)
   - `status`: Returns the number of indexes mapped for the skill (`/rag status all` or `/rag status dev/skills/devops`)
   - `reindex`: Triggers the indexer to overwrite the centralized metadata for the plugin (`/rag reindex dev`)
   - `cleanup`: Deletes the centralized `symbols.yaml` and RAG index directory for the plugin (`/rag cleanup dev`)
   - `purge`: Alias for destructive cleanup when you want an explicit reset verb (`/rag purge all`)
   
// turbo-all
3. You should parse the action and call the appropriate MCP tool: `search-skill-knowledge`, `rag-status`, `rag-reindex`, `rag-cleanup`, `rag-purge`.
4. The `<skill>` parameter expects paths like `ai`, `dev`, `core`, `all`, or deeper skills like `ai/skills/rag`. Generated output is stored centrally under `~/Library/Application Support/Augur/rag/`.
5. If the outcome indicates an error, automatically read standard output and notify the user.
6. Print the JSON output generated from the MCP tool nicely formatted.
