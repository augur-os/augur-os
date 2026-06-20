from src.lib.brain_classify.route import target_brain_for_sources


def test_project_sources_route_to_project():
    assert target_brain_for_sources(["src/mcp/augur_core/server.py", "ADR-781"]) == "project"


def test_private_sources_route_to_personal():
    assert (
        target_brain_for_sources(["Au-vault/capabilities/skills/resume-tailor/SKILL.md", "Au-docs/career/resumes/x.md"])
        == "personal"
    )


def test_mixed_no_clear_majority_defaults_personal():
    # Personal-default avoids leaking borderline personal knowledge into the
    # publicly-tracked project repo (privacy-safe default).
    assert target_brain_for_sources([]) == "personal"
