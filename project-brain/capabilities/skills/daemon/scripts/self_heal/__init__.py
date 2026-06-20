"""Self-heal sub-modules extracted from ai_self_healer.py.

Modules:
- classifier: LLM-based severity classification and pattern matching
- escalation: Dedup, TODO markers, critical items, fix prompts
- fixers: Lock management, headless fix invocation, shell actions
- patterns: Shared constants (watermark filename, line limits)
- pipeline: Main scan->classify->route->act orchestration
- registry: Issue registry persistence (load/save/compact)
- router: Issue routing (fix vs. TODO vs. dismiss)
- scanner: Log scanning, watermarks, dedup keys, resource health, discovery
"""
