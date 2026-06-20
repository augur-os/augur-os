"""
Skill discovery tool implementations.

Tools for listing, finding, and loading skills and their modules.

This module is the stable public surface: it re-exports the 12 ``*_impl``
functions from cohesive sibling modules so existing imports
(``from .skills import ...``) keep working unchanged. The implementations
live in:

- ``skills_common`` — shared helpers and constants (leaf module).
- ``skills_read``   — list/get/find/health.
- ``skills_docs``   — module/reference/config/doc read+write.
- ``skills_vault``  — actions/vault-notes/reindex.
"""

# Shared helpers + constants (re-exported for callers/tests that reference
# them on the ``skills`` module, e.g. via monkeypatch).
from .skills_common import (
    GENERATED_CLIENT_DIRS,
    GENERATED_DOC_MARKER,
    _generated_source_path,
    _get_data_dir,
    _get_skills_dir,
    _is_generated_skill_doc,
    _resolve_skill_note_brain_id,
    _strip_generated_header,
)
from .skills_docs import (
    get_config_impl,
    get_skill_doc_impl,
    load_module_impl,
    load_reference_impl,
    update_skill_doc_impl,
)
from .skills_read import (
    find_skill_impl,
    get_skill_health_impl,
    get_skill_impl,
    list_skills_impl,
)
from .skills_vault import (
    list_skill_actions_impl,
    list_skill_vault_notes_impl,
    reindex_browse_category_impl,
)

__all__ = [
    "list_skills_impl",
    "get_skill_impl",
    "load_module_impl",
    "load_reference_impl",
    "get_config_impl",
    "find_skill_impl",
    "get_skill_health_impl",
    "list_skill_actions_impl",
    "get_skill_doc_impl",
    "update_skill_doc_impl",
    "list_skill_vault_notes_impl",
    "reindex_browse_category_impl",
    # Internal helpers + constants (re-exported for stable monkeypatch surface)
    "_resolve_skill_note_brain_id",
    "_is_generated_skill_doc",
    "_generated_source_path",
    "_strip_generated_header",
    "_get_skills_dir",
    "_get_data_dir",
    "GENERATED_DOC_MARKER",
    "GENERATED_CLIENT_DIRS",
]
