import argparse
import src.cli as cli


def test_dev_build_handler_invokes_engine(monkeypatch, capsys):
    import src.lib.dev_build as dev_build

    monkeypatch.setattr(
        dev_build, "run_dev_build", lambda **k: {"ok": True, "port": 3000, "url": "http://localhost:3000/"}
    )
    rc = cli._handle_dev(argparse.Namespace(dev_command="build"), [])
    assert rc == 0
    assert "3000" in capsys.readouterr().out


def test_dev_build_handler_returns_1_on_failure(monkeypatch, capsys):
    import src.lib.dev_build as dev_build

    monkeypatch.setattr(
        dev_build, "run_dev_build", lambda **k: {"ok": False, "reason": "gate denied: compiling", "port": 3000}
    )
    rc = cli._handle_dev(argparse.Namespace(dev_command="build"), [])
    assert rc == 1
