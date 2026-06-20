from src.lib.brain_classify.evidence import extract_brain_evidence, BrainEvidence


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_private_subject_entry_reads_personal(tmp_path):
    # The resume-tailor case: engineering-dense prose, private subject.
    f = _write(
        tmp_path,
        "resume-tailor-skill.md",
        "Built a private-vault skill at `Au-vault/capabilities/skills/resume-tailor/`\n"
        "that tailors Gur's resume and writes to `Au-docs/career/resumes/`.\n"
        "See [[resume-no-founder-positioning]] and [[canonical-resumes-location]].\n",
    )
    ev = extract_brain_evidence(f)
    assert isinstance(ev, BrainEvidence)
    assert ev.personal_refs >= 3
    assert ev.subject_brain == "personal"


def test_project_subject_entry_reads_project(tmp_path):
    f = _write(
        tmp_path,
        "mcp-shim.md",
        "The augur_core MCP server in `src/mcp/augur_core/` exposes two module objects.\n"
        "Fix in `src/mcp/augur_framework/__main__.py`; see ADR-781.\n",
    )
    ev = extract_brain_evidence(f)
    assert ev.project_refs >= 2
    assert ev.subject_brain == "project"


def test_no_artifact_refs_is_ambiguous(tmp_path):
    f = _write(tmp_path, "thoughts.md", "A general reflection with no paths or links.\n")
    ev = extract_brain_evidence(f)
    assert ev.subject_brain == "ambiguous"


def test_signals_are_human_readable(tmp_path):
    f = _write(tmp_path, "x.md", "Touches `src/mcp/` and `Au-vault/career/`.\n")
    ev = extract_brain_evidence(f)
    assert any("src/mcp" in s for s in ev.signals)
    assert any("Au-vault/career" in s for s in ev.signals)


def test_frontmatter_citations_do_not_flip_subject(tmp_path):
    # A project page that CITES vault sources in frontmatter stays project.
    f = tmp_path / "advisor.md"
    f.write_text(
        "---\n"
        "title: Advisor System\n"
        "_sources:\n"
        "- '[[vault:/Users/x/Projects/Au-vault/skills/advisor/SKILL.md]]'\n"
        "- '[[vault:/Users/x/Projects/Au-vault/skills/advisor/modules/cost.md]]'\n"
        "---\n"
        "The advisor skill analyzes `src/mcp/augur_core/` usage and dashboard metrics.\n",
        encoding="utf-8",
    )
    ev = extract_brain_evidence(f)
    assert ev.subject_brain == "project"


def test_body_citation_scheme_refs_are_ignored(tmp_path):
    f = tmp_path / "x.md"
    f.write_text(
        "Discusses `src/config/paths.py` routing.\n" "See Also: [[vault:/Users/x/Projects/Au-vault/notes/a.md]]\n",
        encoding="utf-8",
    )
    ev = extract_brain_evidence(f)
    assert ev.subject_brain == "project"
