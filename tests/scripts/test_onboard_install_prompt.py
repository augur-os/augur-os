from src.config.paths import get_skill_root


def test_install_prompt_asks_exactly_one_initial_question() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "Which folder should I initialize?" in text
    assert text.count("Which folder should I initialize?") == 1
    assert "Get to know your AI setup, build your local second brain, and talk with your projects." in text
    assert "Setup takes about 3 minutes." not in text
    assert "Welcome to Augur — your AI-powered second brain." not in text


def test_install_prompt_gets_folder_answer_before_install_command() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    question_pos = text.index("Which folder should I initialize?")
    # The execution section that runs the onboard engine (aug onboard run) must come after
    # the folder question; the preamble references the command earlier for documentation.
    install_command_pos = text.index("### 2a: Run the onboard engine")

    assert question_pos < install_command_pos
    assert "wait for the answer" in text[:install_command_pos].lower()


def test_install_prompt_gets_folder_answer_before_windows_bootstrap() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    question_pos = text.index("Which folder should I initialize?")
    windows_bootstrap_pos = text.index("windows-one-click-bootstrap.ps1")
    windows_section = text.split("## Windows one-click setup", 1)[1].split("## Step 2", 1)[0]

    assert question_pos < windows_bootstrap_pos
    assert "folder answer is already collected" in windows_section
    assert "allowed pauses after the folder answer" in windows_section
    assert "prompts for either an existing vault git repo" not in windows_section


def test_install_prompt_names_pause_policy_and_browse_fallback() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "If none match, ask the user." not in text
    assert "ask how they want to proceed" not in text
    assert "auto-fix missing non-sensitive prerequisites" in text
    assert "pause only for credentials, OS permissions, or destructive ambiguity" in text
    assert "open Browse" in text
    assert "http://localhost:3000/browse" in text
    assert "Ask Augur about this project" in text
    assert "do not save or retain anything unless the user asks" in text


def test_install_prompt_leads_with_fast_launch_folder_inventory() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "choose a folder" in text.lower()
    assert "aug init --project" in text
    assert "uv run aug init --project" in text
    assert "AI artifact inventory" in text
    assert "inventory-only" in text.lower()


def test_install_prompt_separates_installer_client_updates_from_folder_projection() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "Installer-owned client integration updates" in text
    assert "chosen folder" in text.lower()
    assert "must not adopt, rewrite, merge, delete, or project into" in text
    assert "uv run aug init --project <folder> --sync" in text
    assert "run_sync=true" in text
    assert "Default `aug init --project <folder>` remains inventory-only" in text


def test_install_prompt_runs_folder_init_instead_of_handing_off_to_user() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")
    step_2b = text.split("### 2b: Initialize the chosen folder", 1)[1]

    assert "Choose a folder to initialize, then run:" not in step_2b
    assert "Ask the user for the folder they want Augur to initialize" in step_2b
    assert "run `uv run aug init --project <folder>` yourself" in step_2b
    assert "from the Augur install directory" in step_2b


def test_onboard_install_prompt_routes_windows_to_one_click_bootstrap() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "Windows one-click setup" in text
    assert "scripts/windows-one-click-bootstrap.ps1" in text
    assert "powershell" in text.lower()


def test_onboard_install_prompt_explains_windows_success_and_logs() -> None:
    text = (get_skill_root("onboard") / "install.md").read_text(encoding="utf-8")

    assert "%LOCALAPPDATA%\\Augur\\setup\\bootstrap.log" in text
    assert "%LOCALAPPDATA%\\Augur\\setup\\bootstrap-state.json" in text
    assert "AUGUR_VAULT_REPO" in text
    assert "AUGUR_VAULT" in text
    assert "-InitLocalVault" in text
    assert "indexes are built" in text
    assert "Ready" in text
    assert "rerun the same PowerShell command" in text
