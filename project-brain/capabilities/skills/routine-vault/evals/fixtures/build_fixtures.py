"""Generate the fake binary-named fixture files for routine-vault evals/tests.

ADR-814 (brain publishable-by-construction) forbids tracking binary-suffixed
files under project-brain/, so the fake .zip/.pptx/.pdf/.png placeholders these
fixtures need are GENERATED here instead of committed. Tracked fixture content
stays text-only (.augur-lifecycle.yaml, .milestones.json, *.md, *.svg);
everything binary-NAMED is a few placeholder bytes written at build time.

Consumers:
- tests/test_hygiene_e2e.py calls ensure_fixtures() before staging a fixture.
- Manual eval runs: `python build_fixtures.py` regenerates everything in place.

Supersedes the old _build_websites.py one-time generator (websites generation
is folded into _WEBSITES_VERSIONED below).
"""
from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

# Static placeholder files: fixture-relative path -> exact bytes.
# Contents replicate the original committed placeholders byte-for-byte so
# scan/apply byte-count assertions stay stable.
_STATIC_FILES: dict[str, bytes] = {
    "fixture_cached_known_group/guriqo-com-V10001.zip": b"PK\n",
    "fixture_cached_known_group/guriqo-com-V10032.zip": b"PK\n",
    "fixture_deploy_root/site-v1.zip": b"v1",
    "fixture_deploy_root/site-v2.zip": b"v2",
    "fixture_format_variants/augur-vision-1.pdf": b"pdf",
    "fixture_format_variants/augur-vision-1.pptx": b"pptx",
    "fixture_lifecycle_malformed_groups/file.zip": b"PK\n",
    "fixture_logos_mixed/augur-logo.png": b"augur-png",
    "fixture_logos_mixed/guriqo-logo.png": b"guriqo-png",
    "fixture_milestone_pinned/deck-v1.pptx": b"v1",
    "fixture_milestone_pinned/deck-v2.pptx": b"v2",
    "fixture_milestone_pinned/deck-v3.pptx": b"v3",
    "fixture_mixed_version_scheme/guriqo-com-V10032.zip": b"PK\n",
    "fixture_mixed_version_scheme/guriqo-com-v33-1.zip": b"PK\n",
    "fixture_mixed_version_scheme/guriqo-com-v45-1.zip": b"PK\n",
    "fixture_variant_suffix/linkedin-banner-personal-augur.png": b"PNG\n",
    "fixture_variant_suffix/linkedin-banner-personal.png": b"PNG\n",
}


def _websites_versioned_files() -> dict[str, bytes]:
    """fixture_websites_versioned: 32 guriqo-com + 18 augur-run fake zips."""
    files: dict[str, bytes] = {}
    for v in range(10001, 10033):
        files[f"fixture_websites_versioned/guriqo-com-V{v}.zip"] = f"guriqo-com-{v}".encode()
    for v in range(10015, 10033):
        files[f"fixture_websites_versioned/augur-run-V{v}.zip"] = f"augur-run-{v}".encode()
    return files


def ensure_fixtures(root: Path | None = None) -> int:
    """Idempotently write all fake binary fixture files. Returns files written."""
    root = root or FIXTURES_DIR
    written = 0
    all_files = {**_STATIC_FILES, **_websites_versioned_files()}
    for rel, content in all_files.items():
        path = root / rel
        if path.exists() and path.read_bytes() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        written += 1
    return written


if __name__ == "__main__":
    count = ensure_fixtures()
    print(f"fixtures ensured ({count} file(s) written) under {FIXTURES_DIR}")
