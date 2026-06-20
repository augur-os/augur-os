"""
Tests for symbol_extractor — extract Python/TypeScript code symbols for RAG indexing.

Module: skills/rag/scripts/symbol_extractor.py
"""

import pytest
import yaml


# ---------------------------------------------------------------------------
# Python symbol extraction
# ---------------------------------------------------------------------------


class TestExtractPythonSymbols:
    """Tests for extract_python_symbols parsing."""

    def test_extracts_top_level_function(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_python_symbols

        f = tmp_path / "mod.py"
        f.write_text("def hello():\n    pass\n")
        symbols = extract_python_symbols(str(f))
        assert len(symbols) == 1
        assert symbols[0] == {"name": "hello", "type": "function"}

    def test_extracts_class_and_methods(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_python_symbols

        f = tmp_path / "mod.py"
        f.write_text(
            "class MyClass:\n"
            "    def method_a(self):\n"
            "        pass\n"
            "    async def method_b(self):\n"
            "        pass\n"
        )
        symbols = extract_python_symbols(str(f))
        names = {s["name"] for s in symbols}
        assert "MyClass" in names
        assert "MyClass.method_a" in names
        assert "MyClass.method_b" in names

    def test_extracts_async_function(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_python_symbols

        f = tmp_path / "mod.py"
        f.write_text("async def fetch_data():\n    pass\n")
        symbols = extract_python_symbols(str(f))
        assert symbols[0]["name"] == "fetch_data"
        assert symbols[0]["type"] == "function"

    def test_returns_empty_for_syntax_error(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_python_symbols

        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n    pass\n")
        symbols = extract_python_symbols(str(f))
        assert symbols == []


# ---------------------------------------------------------------------------
# TypeScript symbol extraction
# ---------------------------------------------------------------------------


class TestExtractTypescriptSymbols:
    """Tests for extract_typescript_symbols regex parsing."""

    def test_extracts_exported_function(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_typescript_symbols

        f = tmp_path / "mod.ts"
        f.write_text("export function greet(name: string): string {\n  return name;\n}\n")
        symbols = extract_typescript_symbols(str(f))
        names = {s["name"] for s in symbols}
        assert "greet" in names

    def test_extracts_interface_and_type(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_typescript_symbols

        f = tmp_path / "types.ts"
        f.write_text(
            "export interface UserProps {\n  name: string;\n}\n\n"
            "export type UserId = string;\n"
        )
        symbols = extract_typescript_symbols(str(f))
        names = {s["name"] for s in symbols}
        assert "UserProps" in names
        assert "UserId" in names

    def test_extracts_const_arrow_function(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_typescript_symbols

        f = tmp_path / "utils.ts"
        f.write_text("export const formatDate = (d: Date) => {\n  return d.toISOString();\n};\n")
        symbols = extract_typescript_symbols(str(f))
        names = {s["name"] for s in symbols}
        assert "formatDate" in names

    def test_extracts_class(self, tmp_path):
        from src.lib.index.symbol_extractor import extract_typescript_symbols

        f = tmp_path / "service.ts"
        f.write_text("export default class DataService {\n  fetch() {}\n}\n")
        symbols = extract_typescript_symbols(str(f))
        names = {s["name"] for s in symbols}
        assert "DataService" in names


# ---------------------------------------------------------------------------
# Directory processing
# ---------------------------------------------------------------------------


class TestProcessDirectory:
    """Tests for process_directory walking and generating symbols.yaml."""

    def test_generates_symbols_yaml(self, tmp_path):
        from src.lib.index.symbol_extractor import process_directory

        # Create a small project tree
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "helper.py").write_text("def helper_func():\n    pass\n")
        (tmp_path / "lib" / "types.ts").write_text("export interface Config { key: string; }\n")

        output_dir = tmp_path / "output"
        yaml_path = process_directory(str(tmp_path), str(output_dir))

        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text())
        assert isinstance(data, dict)
        # Should have entries for both files
        assert any("helper.py" in k for k in data)
        assert any("types.ts" in k for k in data)

    def test_skips_node_modules(self, tmp_path):
        from src.lib.index.symbol_extractor import process_directory

        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.ts").write_text("export function npmFunc() {}\n")

        output_dir = tmp_path / "output"
        yaml_path = process_directory(str(tmp_path), str(output_dir))

        data = yaml.safe_load(yaml_path.read_text())
        # node_modules content should be excluded
        assert data is None or not any("node_modules" in k for k in (data or {}))

    def test_skips_git_directory(self, tmp_path):
        from src.lib.index.symbol_extractor import process_directory

        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        (git_dir / "pre-commit.py").write_text("def hook():\n    pass\n")

        output_dir = tmp_path / "output"
        yaml_path = process_directory(str(tmp_path), str(output_dir))

        data = yaml.safe_load(yaml_path.read_text())
        assert data is None or not any(".git" in k for k in (data or {}))
