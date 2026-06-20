def test_get_rag_category_dir_returns_category_subdir():
    from src.config.paths import get_rag_category_dir, get_rag_dir

    result = get_rag_category_dir("skills")
    assert result == get_rag_dir() / "skills"


def test_get_rag_category_dir_all_categories():
    from src.config.paths import get_rag_category_dir, get_rag_dir

    categories = [
        "skills",
        "adrs",
        "actions",
        "prompts",
        "vault",
        "documents",
        "agents",
        "integrations",
        "commands",
        "mcp-tools",
        "scripts",
        "api-routes",
        "tests",
        "pages",
        "blocks",
        "logs",
    ]
    for cat in categories:
        result = get_rag_category_dir(cat)
        assert result == get_rag_dir() / cat
