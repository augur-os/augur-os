import re
from pathlib import Path

SCRIPT = Path("scripts/windows-one-click-bootstrap.ps1")


def _function_body(text: str, name: str) -> str:
    match = re.search(
        rf"function {re.escape(name)} \{{(?P<body>.*?)(?=^function |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"missing function {name}"
    return match.group("body")


def test_bootstrap_script_exists_and_has_dry_run_mode():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "param(" in text
    assert "[string]$RepoUrl" in text
    assert "[string]$VaultRepo" in text
    assert "[string]$VaultDir" in text
    assert "AUGUR_REPO_URL" in text
    assert "AUGUR_VAULT_REPO" in text
    assert "AUGUR_VAULT" in text
    # A fresh public-user one-click bootstrap defaults to the PUBLIC repo, not the
    # owner's private dev repo (gsannikov/augur).
    assert "https://github.com/augur-os/augur-os.git" in text
    assert "gsannikov/augur" not in text
    assert "[switch]$DryRun" in text
    assert "[switch]$NoLaunch" in text
    assert "[switch]$InitLocalVault" in text
    assert "[switch]$NoVaultPrompt" in text
    assert "bootstrap-state.json" in text


def test_bootstrap_uses_winget_for_supported_prerequisites():
    text = SCRIPT.read_text(encoding="utf-8")
    prerequisites = _function_body(text, "Ensure-Prerequisites")

    assert "Git.Git" in text
    assert "Python.Python.3.11" in text
    assert "OpenJS.NodeJS.LTS" in text
    assert "winget install --id" in text
    assert "Test-PythonAvailable" in text
    assert "WindowsApps" in text
    assert "python3.exe" in text
    python_command = _function_body(text, "Get-PythonCommand")
    assert "3.11" in python_command
    assert re.search(r"Get-Command\s+\$candidate\s+-All\b", python_command)
    assert re.search(
        r"if\s+\(-not\s+\(Test-PythonAvailable\)\)\s*\{.*?Python\.Python\.3\.11.*?-ForceInstall",
        prerequisites,
        re.DOTALL,
    )


def test_bootstrap_installs_codex_via_current_npm_channel():
    text = SCRIPT.read_text(encoding="utf-8")
    ensure_codex = _function_body(text, "Ensure-Codex")

    assert "npm i -g @openai/codex@latest" in text
    assert "codex_login_completed" in text
    assert re.search(r'Invoke-Step\s+@\(\s*"codex",\s*"login"\s*\)', ensure_codex)
    assert re.search(
        r"if\s+\(-not\s+\(Get-StateValue\s+\"codex_login_completed\"\)\)",
        ensure_codex,
    )
    assert re.search(
        r"Invoke-Step\s+@\(\s*\"codex\",\s*\"login\"\s*\).*?if\s+\(-not\s+\$DryRun\)\s*\{.*?codex_login_completed\s*=\s*\$true",
        ensure_codex,
        re.DOTALL,
    )
    assert "NoLaunch" not in ensure_codex


def test_bootstrap_hands_off_to_repo_owned_orchestrator():
    text = SCRIPT.read_text(encoding="utf-8")
    handoff = _function_body(text, "Invoke-CodexHandoff")

    assert "project-brain\\capabilities\\skills\\onboard\\scripts\\windows_one_click.py" in text
    assert '"skills\\onboard\\scripts\\windows_one_click.py"' not in text
    assert "--run" in text
    assert "Local orchestrator command" in handoff
    assert "Invoke-Step $orchestratorCommand" in handoff
    assert "codex exec" not in handoff
    assert "Assert-PythonAvailable" in handoff
    assert "--vault-repo" in handoff
    assert "--vault-dir" in handoff
    assert "--init-local-vault" in handoff
    assert "--no-vault-prompt" in handoff


def test_existing_checkout_refuses_wrong_origin():
    text = SCRIPT.read_text(encoding="utf-8")
    ensure_repo = _function_body(text, "Ensure-Repo")

    assert "remote get-url origin" in ensure_repo
    assert "Refusing to switch repositories" in ensure_repo


def test_successful_completion_clears_stale_failure_state():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "ClearKeys" in _function_body(text, "Write-State")
    assert re.search(
        r"completed\s*=\s*\$true.*?blocked\s*=\s*\$false.*?handoff_completed\s*=\s*\$true.*?-ClearKeys\s+@\(\"error\",\s*\"blocked_reason\",\s*\"missing_package\",\s*\"completion_reason\"\)",
        text,
        re.DOTALL,
    )


def test_skipped_handoff_does_not_mark_bootstrap_complete():
    text = SCRIPT.read_text(encoding="utf-8")
    handoff = _function_body(text, "Invoke-CodexHandoff")

    assert re.search(r"if\s+\(\$NoLaunch\s+-or\s+\$DryRun\).*?return\s+\$false", handoff, re.DOTALL)
    assert "handoff_skipped" in text
    assert re.search(
        r"completed\s*=\s*\$false.*?blocked\s*=\s*\$false.*?handoff_skipped\s*=\s*\$true.*?completion_reason\s*=\s*\"codex_handoff_skipped\"",
        text,
        re.DOTALL,
    )
