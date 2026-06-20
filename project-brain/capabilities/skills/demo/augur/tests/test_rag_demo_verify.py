from __future__ import annotations


def test_verify_demo_rag_returns_compact_hits(tmp_path, monkeypatch) -> None:
    from src.lib.ingest import rag_demo_verify

    long_content = "x" * 260
    vault_dir = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    calls: dict[str, object] = {}

    def fake_iterative_search(
        query,
        source_dirs,
        priority_dirs,
        rag_dirs,
        top_k=10,
        include_globs=None,
    ):
        calls["query"] = query
        calls["source_dirs"] = source_dirs
        calls["priority_dirs"] = priority_dirs
        calls["rag_dirs"] = rag_dirs
        calls["top_k"] = top_k
        calls["include_globs"] = include_globs
        return [
            {
                "type": "user_data",
                "hits": [
                    {
                        "file": "vault/sources/files/demo.md",
                        "line": 42,
                        "content": long_content,
                        "scope": "rag",
                        "score": 0.99,
                    }
                ],
            }
        ]

    monkeypatch.setattr(rag_demo_verify, "get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr(rag_demo_verify, "get_rag_dir", lambda: rag_dir)
    monkeypatch.setattr(rag_demo_verify, "rag_iterative_search", fake_iterative_search)

    result = rag_demo_verify.verify_demo_rag("investor demo meeting", top_k=3)

    assert calls == {
        "query": "investor demo meeting",
        "source_dirs": [],
        "priority_dirs": [vault_dir],
        "rag_dirs": [rag_dir],
        "top_k": 3,
        "include_globs": [],
    }
    assert result == {
        "query": "investor demo meeting",
        "hit_count": 1,
        "hits": [
            {
                "file": "vault/sources/files/demo.md",
                "line": "42",
                "content": long_content[:240],
                "scope": "rag",
            }
        ],
        "ready": True,
    }


def test_verify_demo_rag_marks_empty_result_not_ready(tmp_path, monkeypatch) -> None:
    from src.lib.ingest import rag_demo_verify

    def fake_iterative_search(
        query,
        source_dirs,
        priority_dirs,
        rag_dirs,
        top_k=10,
        include_globs=None,
    ):
        return []

    monkeypatch.setattr(rag_demo_verify, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(rag_demo_verify, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(rag_demo_verify, "rag_iterative_search", fake_iterative_search)

    result = rag_demo_verify.verify_demo_rag("investor demo meeting")

    assert result["hit_count"] == 0
    assert result["hits"] == []
    assert result["ready"] is False


def test_verify_demo_rag_filters_to_expected_files(tmp_path, monkeypatch) -> None:
    from src.lib.ingest import rag_demo_verify

    def fake_iterative_search(
        query,
        source_dirs,
        priority_dirs,
        rag_dirs,
        top_k=10,
        include_globs=None,
    ):
        return [
            {
                "type": "user_data",
                "hits": [
                    {"file": "vault/sources/files/old-demo.md", "content": "investor demo meeting"},
                    {
                        "file": "C:/Vault/sources/files/current-demo-meeting.md",
                        "content": "investor demo meeting",
                    },
                ],
            }
        ]

    monkeypatch.setattr(rag_demo_verify, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(rag_demo_verify, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(rag_demo_verify, "rag_iterative_search", fake_iterative_search)

    result = rag_demo_verify.verify_demo_rag(
        "investor demo meeting",
        expected_files=["C:/Vault/sources/files/current-demo-meeting.md"],
    )

    assert result["hit_count"] == 1
    assert result["ready"] is True
    assert result["hits"][0]["file"] == "C:/Vault/sources/files/current-demo-meeting.md"


def test_verify_demo_rag_searches_current_vault_artifacts_through_pipeline(
    tmp_path,
    monkeypatch,
) -> None:
    from src.lib.ingest import rag_demo_verify

    vault_dir = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    current = vault_dir / "sources" / "extracted" / "current-demo-meeting.transcript.md"
    old = vault_dir / "sources" / "extracted" / "old-demo-meeting.transcript.md"
    current.parent.mkdir(parents=True)
    rag_dir.mkdir()
    current.write_text("investor demo meeting", encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_iterative_search(
        query,
        source_dirs,
        priority_dirs,
        rag_dirs,
        top_k=10,
        include_globs=None,
    ):
        calls["query"] = query
        calls["source_dirs"] = source_dirs
        calls["priority_dirs"] = priority_dirs
        calls["rag_dirs"] = rag_dirs
        calls["top_k"] = top_k
        calls["include_globs"] = include_globs
        return [
            {
                "type": "user_data",
                "hits": [
                    {
                        "file": str(old),
                        "line": "2",
                        "content": "old investor demo meeting",
                    },
                    {
                        "file": str(current),
                        "line": "1",
                        "content": "current investor demo meeting",
                    },
                ],
            }
        ]

    monkeypatch.setattr(rag_demo_verify, "get_vault_dir", lambda: vault_dir, raising=False)
    monkeypatch.setattr(rag_demo_verify, "get_rag_dir", lambda: rag_dir, raising=False)
    monkeypatch.setattr(
        rag_demo_verify,
        "rag_iterative_search",
        fake_iterative_search,
        raising=False,
    )

    result = rag_demo_verify.verify_demo_rag(
        "investor demo meeting",
        top_k=3,
        expected_files=[str(current)],
    )

    assert calls == {
        "query": "investor demo meeting",
        "source_dirs": [],
        "priority_dirs": [current.parent, vault_dir],
        "rag_dirs": [rag_dir],
        "top_k": 50,
        "include_globs": [current.name],
    }
    assert result["ready"] is True
    assert result["hit_count"] == 1
    assert result["hits"][0]["file"] == str(current)
