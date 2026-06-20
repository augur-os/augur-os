"""Guard against reintroducing root-skill `.config` files."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_root_skills_do_not_use_dot_config_files():
    skills_dir = PROJECT_ROOT.joinpath("skills")
    violations = sorted(str(path.relative_to(PROJECT_ROOT)) for path in skills_dir.glob("*/.config"))
    assert violations == [], "Root skills must not store local state in `.config` files. " f"Found: {violations}"
