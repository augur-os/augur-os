"""Vault-note frontmatter write helpers for Augur-managed metadata."""
from __future__ import annotations

from src.lib.frontmatter_utils import (
    VAULT_SYSTEM_FIELD_MAP as SYSTEM_FIELD_MAP,
    merge_vault_frontmatter,
    write_vault_frontmatter,
)

__all__ = ["SYSTEM_FIELD_MAP", "merge_vault_frontmatter", "write_vault_frontmatter"]
