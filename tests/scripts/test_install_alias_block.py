from __future__ import annotations

from pathlib import Path

from tests.scripts.launcher_test_utils import run_bash_script

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = PROJECT_ROOT / "scripts" / "install.sh"
MARKER = "# === augur CLI shortcuts (ca/xa/ga) ==="
END_MARKER = "# === end augur CLI shortcuts ==="


def _slash_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def test_install_block_delegates_to_launchers() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")

    assert "xa-launch.sh" in text, "installer must reference scripts/xa-launch.sh"
    assert "ca-launch.sh" in text, "installer must reference scripts/ca-launch.sh"
    assert "ga-launch.sh" in text, "installer must reference scripts/ga-launch.sh"
    assert "gca-launch.sh" in text, "installer must reference scripts/gca-launch.sh"

    block_start = text.index("$marker\n")
    block_end = text.index("$end_marker", block_start)
    block = text[block_start:block_end]

    assert "codex --dangerously-bypass-approvals-and-sandbox" not in block
    assert "xa-launch.sh" in block
    assert "xa --desktop" in text
    assert "ca-launch.sh" in block
    assert "ga-launch.sh" in block
    assert "gca-launch.sh" in block
    assert "unalias ca xa ga gca" in block


def test_installer_rewrites_existing_block(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    rc.write_text(
        "# preexisting line\n"
        f"{MARKER}\n"
        'ca() { claude --dangerously-skip-permissions "$@"; }\n'
        'xa() { codex --dangerously-bypass-approvals-and-sandbox "$@"; }\n'
        'ga() { gemini --yolo "$@"; }\n'
        f"{END_MARKER}\n"
        "# trailing line\n",
        encoding="utf-8",
    )

    source = INSTALL_SH.read_text(encoding="utf-8").replace(
        '\nmain "$@"\n',
        "\n# main disabled by test harness\n",
    )
    harness = tmp_path / "install-harness.sh"
    harness.write_text(
        source
        + "\n"
        + f'export HOME="{_slash_path(tmp_path)}"\n'
        + 'export SHELL="/bin/bash"\n'
        + f'INSTALL_DIR="{_slash_path(PROJECT_ROOT)}"\n'
        + "install_cli_aliases\n",
        encoding="utf-8",
    )

    result = run_bash_script(harness, cwd=PROJECT_ROOT)

    assert result.returncode == 0, result.stderr
    text = rc.read_text(encoding="utf-8")
    assert "# preexisting line" in text
    assert "# trailing line" in text
    assert text.count(MARKER) == 1
    assert "codex --dangerously-bypass-approvals-and-sandbox" not in text
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/xa-launch.sh' in text
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/gca-launch.sh' in text
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/ca-launch.sh' in text
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/ga-launch.sh' in text


def test_installer_removes_legacy_ai_launch_aliases(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    rc.write_text(
        "# preexisting line\n"
        "alias gca='git commit -v -a'\n"
        'alias ca="cd ~/Projects/Augur/ && scripts/ai-launch.sh -- claude --dangerously-skip-permissions"\n'
        'alias ga="cd ~/Projects/Augur/ && scripts/ai-launch.sh -- gemini --approval-mode yolo"\n'
        'alias xa="cd ~/Projects/Augur/ && scripts/ai-launch.sh -- codex --dangerously-bypass-approvals-and-sandbox"\n'
        "# trailing line\n",
        encoding="utf-8",
    )

    source = INSTALL_SH.read_text(encoding="utf-8").replace(
        '\nmain "$@"\n',
        "\n# main disabled by test harness\n",
    )
    harness = tmp_path / "install-harness.sh"
    harness.write_text(
        source
        + "\n"
        + f'export HOME="{_slash_path(tmp_path)}"\n'
        + 'export SHELL="/bin/bash"\n'
        + f'INSTALL_DIR="{_slash_path(PROJECT_ROOT)}"\n'
        + "install_cli_aliases\n",
        encoding="utf-8",
    )

    result = run_bash_script(harness, cwd=PROJECT_ROOT)

    assert result.returncode == 0, result.stderr
    text = rc.read_text(encoding="utf-8")
    assert "# preexisting line" in text
    assert "# trailing line" in text
    assert "scripts/ai-launch.sh" not in text
    assert text.count(MARKER) == 1
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/xa-launch.sh' in text
    assert f'{_slash_path(PROJECT_ROOT)}/scripts/gca-launch.sh' in text
    assert "alias gca='git commit -v -a'" in text
