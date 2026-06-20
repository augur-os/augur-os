from __future__ import annotations

import argparse
import ast
import os
import re
from pathlib import Path

import yaml

IGNORED_PARTS = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}


def extract_python_symbols(filepath: str) -> list[dict]:
    symbols = []
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append({"name": node.name, "type": "class"})
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append({"name": f"{node.name}.{child.name}", "type": "method"})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append({"name": node.name, "type": "function"})
    except Exception:
        pass
    return symbols


def extract_typescript_symbols(filepath: str) -> list[dict]:
    symbols = []
    class_pattern = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_]+)", re.MULTILINE)
    func_pattern = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Za-z0-9_]+)", re.MULTILINE)
    interface_pattern = re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z0-9_]+)", re.MULTILINE)
    type_pattern = re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z0-9_]+)", re.MULTILINE)
    const_func_pattern = re.compile(
        r"^\s*(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[^=]*?)\s*=>",
        re.MULTILINE,
    )

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        for match in class_pattern.finditer(content):
            symbols.append({"name": match.group(1), "type": "class"})
        for match in func_pattern.finditer(content):
            symbols.append({"name": match.group(1), "type": "function"})
        for match in interface_pattern.finditer(content):
            symbols.append({"name": match.group(1), "type": "interface"})
        for match in type_pattern.finditer(content):
            symbols.append({"name": match.group(1), "type": "type"})
        for match in const_func_pattern.finditer(content):
            symbols.append({"name": match.group(1), "type": "function"})
    except Exception:
        pass

    return symbols


def process_directory(directory: str, output_dir: str | None = None) -> Path:
    dir_path = Path(directory).resolve()
    target_dir = Path(output_dir).resolve() if output_dir else dir_path
    target_dir.mkdir(parents=True, exist_ok=True)

    all_symbols: dict[str, list[dict]] = {}

    for root, _, files in os.walk(dir_path):
        root_path = Path(root)
        if any(ignored in root_path.parts for ignored in IGNORED_PARTS):
            continue
        try:
            root_path.relative_to(target_dir)
            continue
        except ValueError:
            pass

        for file in files:
            filepath = root_path / file
            rel_path = filepath.relative_to(dir_path).as_posix()
            if file.endswith(".py"):
                syms = extract_python_symbols(str(filepath))
            elif file.endswith((".ts", ".tsx")):
                syms = extract_typescript_symbols(str(filepath))
            else:
                syms = []
            if syms:
                all_symbols[rel_path] = syms

    yaml_path = target_dir / "symbols.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(all_symbols, f, default_flow_style=False, sort_keys=False)
    print(f"Generated {yaml_path}")
    return yaml_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract code symbols and write symbols.yaml")
    parser.add_argument("directory", help="The directory to parse for symbols")
    parser.add_argument("--output-dir", help="Central output directory for generated metadata")
    args = parser.parse_args()
    process_directory(args.directory, args.output_dir)
