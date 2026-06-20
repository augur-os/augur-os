from routine_orchestrator import goal_catalog, goal_suggest


def _fake_scan(findings_by_loop):
    def _scan(loop_name, *, project_root=None, **_):
        if isinstance(findings_by_loop.get(loop_name), Exception):
            raise findings_by_loop[loop_name]
        return list(findings_by_loop.get(loop_name, []))
    return _scan


def test_assess_aggregates_findings_per_loop():
    scan = _fake_scan({"testing": [{"detail": "build broke"}], "code-quality": []})
    result = goal_suggest.assess(["testing", "code-quality"], project_root=".", scan=scan)
    assert result["testing"] == [{"detail": "build broke"}]
    assert result["code-quality"] == []


def test_assess_isolates_a_crashing_scanner():
    scan = _fake_scan({"testing": RuntimeError("boom"), "code-quality": [{"detail": "x"}]})
    result = goal_suggest.assess(["testing", "code-quality"], project_root=".", scan=scan)
    assert result["testing"] == []
    assert result["code-quality"] == [{"detail": "x"}]


def test_assess_records_timeout_as_bounded_finding():
    def _timeout_scan(loop_name, *, project_root=None, **_):
        raise goal_suggest._ScanDeadlineExpired("slow")

    result = goal_suggest.assess(
        ["testing"],
        project_root=".",
        scan=_timeout_scan,
        per_loop_timeout_seconds=2,
    )
    assert result["testing"][0]["auto_command"] == "goal-suggest-timeout"
    assert result["testing"][0]["goal_suggest_timeout"] is True
    assert "2s" in result["testing"][0]["detail"]


def test_suggest_does_not_count_timeout_markers_toward_finding_count():
    """Timeout markers must NOT inflate finding_count — they carry no real debt signal.

    The goal must still appear as partial=True so the user knows the count is a floor.
    Previously this returned [] (silently dropped), which was the bug being fixed.
    """
    specs = [goal_catalog.GoalSpec(id="harden", title="Harden", loops=("testing",))]
    scan = _fake_scan(
        {
            "testing": [
                {
                    "detail": "scan timed out after 2s",
                    "goal_suggest_timeout": True,
                }
            ]
        }
    )
    suggestions = goal_suggest.suggest(project_root=".", scan=scan, specs=specs)
    # Goal must appear (partial) — not silently dropped
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.finding_count == 0   # timeout marker NOT counted as a real finding
    assert s.partial is True      # but marked partial so user knows the floor is unreliable


def test_suggest_ranks_by_finding_count_and_skips_clean_goals():
    specs = [
        goal_catalog.GoalSpec(id="big", title="Big", loops=("testing", "code-quality")),
        goal_catalog.GoalSpec(id="small", title="Small", loops=("page-health",)),
        goal_catalog.GoalSpec(id="empty", title="Empty", loops=("knowledge-enrichment",)),
    ]
    scan = _fake_scan({
        "testing": [{"detail": "a"}, {"detail": "b"}, {"detail": "c"}],
        "code-quality": [],
        "page-health": [{"detail": "p"}],
        "knowledge-enrichment": [],
    })
    suggestions = goal_suggest.suggest(project_root=".", scan=scan, specs=specs)
    ids = [s.id for s in suggestions]
    assert ids == ["big", "small"]          # ranked desc by count; "empty" dropped
    assert suggestions[0].finding_count == 3
    assert suggestions[1].finding_count == 1


def test_suggest_empty_when_everything_clean():
    scan = _fake_scan({})
    assert goal_suggest.suggest(project_root=".", scan=scan) == []


# --- Issue 1: timed-out loops must be flagged as partial, not silently clean ---


def _timeout_scan_for(timed_out_loops):
    """Return a scan fn that times out for listed loops, empty for others."""
    def _scan(loop_name, *, project_root=None, **_):
        if loop_name in timed_out_loops:
            raise goal_suggest._ScanDeadlineExpired("slow")
        return []
    return _scan


def test_suggest_marks_goal_partial_when_any_loop_timed_out():
    """A goal whose loop scan is cut off must surface as partial=True, not be silently dropped."""
    specs = [goal_catalog.GoalSpec(id="harden", title="Harden", loops=("testing", "hardening"))]
    scan = _timeout_scan_for({"testing"})
    suggestions = goal_suggest.suggest(
        project_root=".", scan=scan, specs=specs, per_loop_timeout_seconds=2
    )
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.partial is True
    assert s.timed_out_loops == ("testing",)


def test_suggest_partial_note_present_when_timed_out():
    """partial_note must be a non-empty string when any loop timed out."""
    specs = [goal_catalog.GoalSpec(id="harden", title="Harden", loops=("testing",))]
    scan = _timeout_scan_for({"testing"})
    suggestions = goal_suggest.suggest(
        project_root=".", scan=scan, specs=specs, per_loop_timeout_seconds=2
    )
    assert len(suggestions) == 1
    assert suggestions[0].partial_note  # non-empty string


def test_suggest_partial_false_and_empty_timed_out_loops_when_no_timeout():
    """When no timeout occurs the suggestion must report partial=False and empty timed_out_loops."""
    specs = [goal_catalog.GoalSpec(id="clean", title="Clean", loops=("testing",))]
    scan = _fake_scan({"testing": [{"detail": "x"}]})
    suggestions = goal_suggest.suggest(project_root=".", scan=scan, specs=specs)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.partial is False
    assert s.timed_out_loops == ()
    assert s.partial_note == ""


def test_suggest_still_shows_real_findings_alongside_partial_flag():
    """When one loop has real findings and another times out, both count and partial are set."""
    specs = [
        goal_catalog.GoalSpec(id="harden", title="Harden", loops=("testing", "hardening"))
    ]
    def _mixed_scan(loop_name, *, project_root=None, **_):
        if loop_name == "hardening":
            raise goal_suggest._ScanDeadlineExpired("slow")
        return [{"detail": "real finding"}]

    suggestions = goal_suggest.suggest(
        project_root=".", scan=_mixed_scan, specs=specs, per_loop_timeout_seconds=2
    )
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.finding_count == 1          # only the real finding
    assert s.partial is True
    assert "hardening" in s.timed_out_loops


def test_suggest_does_not_drop_all_timeout_goal_silently():
    """A goal where ALL loops timed out must still appear in suggestions as partial."""
    specs = [goal_catalog.GoalSpec(id="harden", title="Harden", loops=("testing",))]
    scan = _timeout_scan_for({"testing"})
    suggestions = goal_suggest.suggest(
        project_root=".", scan=scan, specs=specs, per_loop_timeout_seconds=2
    )
    # Previously it was dropped (count==0 after filtering markers). Now it must appear.
    assert len(suggestions) == 1
    assert suggestions[0].partial is True
    assert suggestions[0].finding_count == 0  # floor; real count unknown
