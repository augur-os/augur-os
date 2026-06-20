import argparse
from pathlib import Path

from src.cli_onboard import register_onboard_subcommands, _handle_onboard_run


def test_subcommand_registers():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    register_onboard_subcommands(sub)
    ns = parser.parse_args(["onboard", "run", "--non-interactive"])
    assert ns.onboard_command == "run"
    assert ns.non_interactive is True


def test_handle_run_returns_zero_when_all_ok(monkeypatch, tmp_path: Path):
    from src.lib.onboard.result import StepResult
    import src.cli_onboard as c

    monkeypatch.setattr(c, "run_onboard", lambda ctx, **kw: [("verify", StepResult.ok("done"))])
    ns = argparse.Namespace(non_interactive=True, project=str(tmp_path))
    assert _handle_onboard_run(ns) == 0


def test_handle_run_returns_one_on_non_ok(monkeypatch, tmp_path: Path):
    from src.lib.onboard.result import StepResult
    import src.cli_onboard as c

    monkeypatch.setattr(c, "run_onboard", lambda ctx, **kw: [("detect_prereqs", StepResult.guide("install uv"))])
    ns = argparse.Namespace(non_interactive=False, project=str(tmp_path))
    assert _handle_onboard_run(ns) == 1


def test_non_interactive_flag_reaches_driver(monkeypatch, tmp_path: Path, capsys):
    """End-to-end through the real driver with a guide step: the --non-interactive
    flag must change the run's behavior (distinct abort messaging) and still
    yield a non-zero exit."""
    from src.lib.onboard.result import StepResult
    import src.lib.onboard.driver as drv

    guide_step = [("detect_prereqs", lambda ctx: StepResult.guide("install uv"))]
    monkeypatch.setattr(drv, "STEPS", guide_step)

    ns = argparse.Namespace(non_interactive=True, project=str(tmp_path))
    rc = _handle_onboard_run(ns)
    out = capsys.readouterr().out
    assert rc == 1
    assert "non-interactive" in out.lower()
    assert "requires manual action" in out.lower()


def test_interactive_run_has_no_abort_message(monkeypatch, tmp_path: Path, capsys):
    from src.lib.onboard.result import StepResult
    import src.lib.onboard.driver as drv

    guide_step = [("detect_prereqs", lambda ctx: StepResult.guide("install uv"))]
    monkeypatch.setattr(drv, "STEPS", guide_step)

    ns = argparse.Namespace(non_interactive=False, project=str(tmp_path))
    rc = _handle_onboard_run(ns)
    out = capsys.readouterr().out
    assert rc == 1  # guide is non-ok -> still non-zero, behavior unchanged
    assert "non-interactive" not in out.lower()
