#!/usr/bin/env python3
"""
Skill Porter

Import (or export) a skill bundle into the Augur repo.

Supported import sources:
  - Zip file containing SKILL.md
  - A standalone SKILL.md file
  - Any URL (zip, raw SKILL.md, or a git repo URL)

On import, this tool:
  - Copies the skill into `plugins/<skill>/`
  - Auto-trims large SKILL.md into `references/` (keeps SKILL.md concise)
  - Generates `plugins/<skill>/README.md` via `generate_skill_readmes.py`
  - Ensures `plugins/<skill>/_dev/` exists with version/changelog/import metadata
  - Creates user data scaffolding relative to data base (via src/lib/config/paths.py)
  - Creates `plugins/<skill>/data-template/` to describe data structure (shareable, no user data)

Sub-modules:
  - porter_utils.py: Constants, path helpers, file iteration
  - porter_markdown.py: Frontmatter, section splitting, SKILL.md trimming
  - porter_source.py: Source preparation (file, URL, git)
  - porter_ops.py: Import/export operations, scaffolding

Usage:
  python src/lib/scripts/skill_porter.py analyze --file /path/to/bundle.zip
  python src/lib/scripts/skill_porter.py apply --file /path/to/bundle.zip --on-conflict overwrite
  python src/lib/scripts/skill_porter.py analyze --url https://example.com/repo.git
  python src/lib/scripts/skill_porter.py export --skill job-analyzer --out /tmp/job-analyzer.zip
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Re-export all public API from sub-modules for backward compatibility
from porter_utils import (  # noqa: F401
    REPO_ROOT,
    PACKAGES_DIR,
    IGNORED_DIRS,
    IGNORED_FILENAMES,
    IGNORED_FILE_REGEXES,
    utc_now_iso,
    slugify,
    is_kebab_case,
    run,
    safe_mkdir,
    should_ignore_path,
    iter_copy_candidates,
    safe_extract_zip,
    find_skill_md,
    choose_skill_md,
)
from porter_markdown import (  # noqa: F401
    parse_frontmatter,
    dump_frontmatter,
    extract_title,
    split_sections,
    extract_commands,
    normalize_description,
    ensure_triggers_in_description,
    trim_skill_markdown,
    extract_storage_tree,
    parse_storage_paths,
)
from porter_source import (  # noqa: F401
    SourceContext,
    download_url_to_file,
    sniff_url_kind,
    prepare_source_from_file,
    extract_github_repo_info,
    prepare_source_from_url,
)
from porter_ops import (  # noqa: F401
    compute_dest_slug,
    ensure_dev_metadata,
    ensure_data_template,
    ensure_user_data_scaffold,
    move_source_readme_to_references,
    write_imported_full_skill,
    generate_readme,
    backup_existing_skill,
    resolve_conflict_slug,
    build_analyze_plan,
    apply_import,
    export_skill,
)


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import/Export Augur skills")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_analyze = sub.add_parser("analyze", help="Analyze an import source (dry run)")
    p_analyze.add_argument("--file", type=str, help="Path to a zip file, SKILL.md, or directory")
    p_analyze.add_argument("--url", type=str, help="URL (zip/raw markdown/git repo) containing SKILL.md")

    p_apply = sub.add_parser("apply", help="Apply an import into plugins/")
    p_apply.add_argument("--file", type=str, help="Path to a zip file, SKILL.md, or directory")
    p_apply.add_argument("--url", type=str, help="URL (zip/raw markdown/git repo) containing SKILL.md")
    p_apply.add_argument(
        "--on-conflict",
        choices=["block", "overwrite", "new_slug", "versioned"],
        default="block",
        help="What to do if plugins/<skill> already exists",
    )
    p_apply.add_argument("--slug", type=str, help="Override skill slug (used with new_slug or to rename)")

    p_export = sub.add_parser("export", help="Export a skill as a shareable zip (no user data)")
    p_export.add_argument("--skill", required=True, type=str, help="Skill slug under plugins/")
    p_export.add_argument("--out", required=True, type=str, help="Output zip path")

    args = parser.parse_args()

    if args.cmd == "export":
        result = export_skill(args.skill, Path(args.out))
        _out(json.dumps(result, indent=2))
        return 0

    if bool(args.file) == bool(args.url):
        raise RuntimeError("Provide exactly one of --file or --url")

    tmp = None
    ctx: SourceContext
    try:
        if args.file:
            ctx, tmp = prepare_source_from_file(Path(args.file))
        else:
            ctx, tmp = prepare_source_from_url(args.url)

        if args.cmd == "analyze":
            plan = build_analyze_plan(ctx)
            _out(json.dumps(plan, indent=2))
            return 0

        if args.cmd == "apply":
            result = apply_import(ctx, on_conflict=args.on_conflict, override_slug=args.slug)
            _out(json.dumps(result, indent=2))
            return 0

        raise RuntimeError(f"Unknown command: {args.cmd}")
    finally:
        if tmp is not None:
            try:
                tmp.cleanup()
            except Exception as exc:
                logger.debug("Failed to clean up temp dir: %s", exc)


if __name__ == "__main__":
    raise SystemExit(main())
