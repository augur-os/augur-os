"""Auto-generated importability test for rag_reindex."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "rag_reindex.py"
_SPEC = importlib.util.spec_from_file_location("rag_reindex_under_test", SCRIPT_PATH)
assert _SPEC and _SPEC.loader
rag_reindex = importlib.util.module_from_spec(_SPEC)
sys.modules["rag_reindex_under_test"] = rag_reindex
_SPEC.loader.exec_module(rag_reindex)


def test_rag_reindex_importable():
    """Verify that rag_reindex can be imported without errors."""
    assert rag_reindex is not None


def test_rag_reindex_fix_skips_contextualization(tmp_path):
    """The full repo reindex path should avoid LLM contextualization during loops."""
    ctx = rag_reindex.OpsContext(project_root=tmp_path)

    captured: dict = {}

    def _reindex_all(root, rag_dir, vault_dir=None, documents_dir=None):
        captured.update(
            {
                "root": root,
                "rag_dir": rag_dir,
                "vault_dir": vault_dir,
                "documents_dir": documents_dir,
            }
        )
        return {"skills": 1}

    with patch("src.config.paths.get_rag_dir", return_value=tmp_path / "rag"), \
         patch("src.lib.index.reindex_all", side_effect=_reindex_all):
        result = rag_reindex.fix(ctx, [{"skill": "rag"}])

    assert result.success is True
    assert "contextualize" not in captured
    assert captured["root"] == tmp_path
