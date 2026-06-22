#!/usr/bin/env python3
"""
Interactive Setup Wizard for Augur.

Provides a friendly, step-by-step setup experience with:
- Progress indicators
- Validation at each step
- Sensible defaults
- Color-coded output
"""
# TODO_CLEANUP: This file is 810 lines — consider splitting into smaller modules


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import os
import sys
import shutil
import json
import requests
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404

def _find_project_root() -> Path:
    """Find the Augur project root from script landmarks, env, or fallback."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "pyproject.toml").is_file()
            and (
                (candidate / "src" / "config" / "paths.py").is_file()
                or (candidate / "config" / "system").is_dir()
            )
        ):
            return candidate

    if env_path := os.environ.get("AUGUR_ROOT"):
        return Path(env_path).expanduser().resolve()

    return Path(__file__).resolve().parents[3]


BOOTSTRAP_ROOT = _find_project_root()
os.environ["AUGUR_ROOT"] = str(BOOTSTRAP_ROOT)
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from src.config.paths import get_launch_agents_dir, get_logs_dir


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


# Inline function to avoid import issues during setup
def _get_project_root() -> Path:
    """Get project root directory."""
    return _find_project_root()


def _get_plist_templates_dir() -> Path:
    return _resolve_daemon_skill_root(_get_project_root()) / "assets" / "plists"


def _resolve_daemon_skill_root(repo_root: Path) -> Path:
    """Resolve the canonical migrated daemon skill root."""
    return repo_root / "project-brain" / "capabilities" / "skills" / "daemon"


def _render_plist_template(template_name: str, replacements: dict[str, str]) -> str:
    template_path = _get_plist_templates_dir() / template_name
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(key, value)
    return content


# Ensure localhost traffic bypasses any corporate proxies
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_PYTHON = (3, 11)
STEPS = [
    "Check Prerequisites",
    "Configure Network/SSL",
    "Verify Python Environment",
    "Install Dependencies",
    "Configure Data Directory",
    "Install Dashboard",
    "Configure Background Services",
    "Setup IDE Bridge",
    "Configure LLM Providers",
    "Validate Setup",
]

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════════════════════


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ""
        cls.CYAN = cls.BOLD = cls.DIM = cls.NC = ""


if not sys.stdout.isatty():
    Colors.disable()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def print_header(text: str):
    _out()
    _out(f"{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.NC}")
    _out(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.NC}")
    _out(f"{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.NC}")
    _out()


def print_progress(step: int, total: int, text: str):
    bar_len = 30
    filled = int(bar_len * step / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = int(100 * step / total)
    _out(f"\n{Colors.BOLD}[{bar}] {pct}% - Step {step}/{total}: {text}{Colors.NC}\n")


def print_step(text: str):
    _out(f"{Colors.BOLD}{Colors.BLUE}▶ {text}{Colors.NC}")


def print_success(text: str):
    _out(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_warning(text: str):
    _out(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")


def print_error(text: str):
    _out(f"{Colors.RED}✗ {text}{Colors.NC}")


def print_info(text: str):
    _out(f"{Colors.CYAN}ℹ {text}{Colors.NC}")


def run_cmd(cmd: list[str], capture: bool = True) -> tuple[int, str]:
    """Run command and return (returncode, output)."""
    try:
        result = _run_command(
            cmd,
            capture_output=capture,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout + result.stderr
    except TimeoutExpired:
        return 1, "Command timed out"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def get_repo_root() -> Path:
    """Find the repository root."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def get_agent_config(data_dir: Path) -> dict:
    config_path = data_dir / ".agent" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            return {}
    return {}


def set_agent_config(data_dir: Path, config: dict):
    agent_dir = data_dir / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_path = agent_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))


def check_connectivity() -> bool:
    print_info("Checking network connectivity...")
    try:
        # Try a known reliable endpoint
        requests.get("https://github.com", timeout=5)
        return True
    except requests.exceptions.SSLError as e:
        print_warning(f"SSL verification failed: {e}")
        return False
    except requests.exceptions.RequestException:
        # Other errors (DNS, Timeout) - unsure, but assume NOT a cert issue for now
        return True
    except Exception:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# WIZARD STEPS
# ═══════════════════════════════════════════════════════════════════════════════


def step_prerequisites() -> bool:
    """Step 1: Check prerequisites."""
    print_step("Checking system prerequisites...")

    checks = [
        ("git", "Version control"),
        ("node", "Dashboard runtime"),
        ("npm", "Package manager"),
    ]

    all_ok = True
    for cmd, desc in checks:
        if check_command(cmd):
            version_cmd = [cmd, "--version"]
            _, version = run_cmd(version_cmd)
            version = version.strip().split("\n")[0]
            print_success(f"{desc}: {version}")
        else:
            print_error(f"{desc} ({cmd}): NOT FOUND")
            all_ok = False

    return all_ok


def step_ssl_check() -> bool:
    """Step 2: Configure Network/SSL."""
    print_step("Configuring network settings...")

    # Resolve Data Dir (Early)
    data_dir = _get_project_root()
    config = get_agent_config(data_dir)

    trust_system_certs = config.get("trust_system_certs", False)

    if trust_system_certs:
        print_info("Corporate SSL workaround enabled via config.")
    else:
        # Auto-detect
        if not check_connectivity():
            print_warning("Enabling corporate SSL workaround automatically.")
            trust_system_certs = True
            config["trust_system_certs"] = True
            set_agent_config(data_dir, config)

    if trust_system_certs:
        # 1. Git Config
        print_info("Configuring Git to use secure channel/system certs...")
        # On Windows 'schannel' is best; on Mac/Linux usually 'osxkeychain' or just ensuring ca-certificates
        # But for 'http.sslBackend', it's Windows specific.
        # On Mac, we might need no-op or specific config.
        # For now, let's strictly handle NPM and generic helpful configs.
        if sys.platform == "win32":
            run_cmd(["git", "config", "--global", "http.sslBackend", "schannel"])

        # 2. NPM Config
        if check_command("npm"):
            print_info("Configuring NPM to disable strict SSL...")
            run_cmd(["npm", "config", "set", "strict-ssl", "false"])
            print_success("NPM configured")

        # 3. Pip Config (Trusted Hosts)
        # We set these for the pip command we use later
        os.environ["PIP_TRUSTED_HOST"] = "pypi.org pypi.python.org files.pythonhosted.org"
        print_success("SSL Workaround Applied")

    return True


def step_python() -> bool:
    """Step 2: Verify Python environment."""
    print_step("Verifying Python environment...")

    # Check Python version
    py_version = sys.version_info[:2]
    if py_version < REQUIRED_PYTHON:
        print_error(
            f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required (found {py_version[0]}.{py_version[1]})"
        )
        return False

    print_success(f"Python {py_version[0]}.{py_version[1]} ✓")

    # Check virtual environment
    repo_root = get_repo_root()
    venv_path = repo_root / ".venv"

    if venv_path.exists():
        print_success(f"Virtual environment: {venv_path}")
    else:
        print_warning("Virtual environment not found, creating...")
        code, output = run_cmd([sys.executable, "-m", "venv", str(venv_path)])
        if code != 0:
            print_error(f"Failed to create venv: {output}")
            return False
        print_success("Virtual environment created")

    return True


def step_dependencies() -> bool:
    """Step 3: Install Python dependencies."""
    print_step("Installing Python dependencies...")

    repo_root = get_repo_root()
    venv_pip = repo_root / ".venv" / "bin" / "pip"

    if not venv_pip.exists():
        venv_pip = repo_root / ".venv" / "Scripts" / "pip.exe"  # Windows

    if not venv_pip.exists():
        print_error("pip not found in virtual environment")
        return False

    # Install from requirements
    requirements = repo_root / "plugins" / "local-rag" / "requirements-dev.txt"
    if requirements.exists():
        print_info(f"Installing from {requirements.name}...")
        code, output = run_cmd([str(venv_pip), "install", "-q", "-r", str(requirements)])
        if code != 0:
            print_warning(f"Some dependencies may have failed: {output[:200]}")

    print_success("Python dependencies installed")
    return True


def step_data_dir() -> bool:
    """Step 4: Configure data directory."""
    print_step("Configuring data directory...")

    # Check for existing data dir
    data_paths = [
        _get_project_root(),
        _get_project_root(),
    ]

    data_dir = None
    for p in data_paths:
        if p.exists():
            data_dir = p
            break

    if data_dir:
        print_success(f"Data directory found: {data_dir}")
    else:
        data_dir = data_paths[0]
        print_info(f"Creating data directory: {data_dir}")

        dirs_to_create = [
            "plugins/dev/platform-admin/backlogs",
            "plugins/dev/advisor",
            "plugins/orchestration/executor/agent-tasks/backlog",
            "admin/channels/inbox",
            "plugins/consulting/career/jobs",
        ]

        for d in dirs_to_create:
            (data_dir / d).mkdir(parents=True, exist_ok=True)

        print_success(f"Data directory created: {data_dir}")

    # Set environment variable
    os.environ["AUGUR_ROOT"] = str(data_dir)
    print_info(f"AUGUR_ROOT={data_dir}")

    return True


def step_dashboard() -> bool:
    """Step 5: Install dashboard and configure auto-start service."""
    print_step("Installing dashboard dependencies...")

    repo_root = get_repo_root()
    dashboard_path = repo_root / "apps" / "dashboard"

    if not dashboard_path.exists():
        dashboard_path = repo_root / "dashboard"

    if not dashboard_path.exists():
        print_warning("Dashboard directory not found, skipping")
        return True

    dashboard_path / "package.json"
    node_modules = dashboard_path / "node_modules"

    if node_modules.exists():
        print_success("Dashboard dependencies already installed")
    else:
        print_info("Running npm install...")
        code, output = run_cmd(["npm", "install"], capture=False)
        if code != 0:
            print_warning("npm install had issues, but continuing...")

    print_success("Dashboard ready")

    # Dashboard supervision is owned by the unified Augur daemon (configured in
    # step_services -> service_healer; ADR-787 Part B in-process supervisor). The
    # dashboard is started through the gate-aware wrapper (`aug dev build` /
    # apps/dashboard/scripts/start-dev.sh) and self-healed by dashboard_monitor.
    #
    # We intentionally do NOT install a standalone `npm run dev` KeepAlive
    # LaunchAgent here: it bypassed the lifecycle gate and port-owner detection,
    # and its KeepAlive could resurrect a stale dev server squatting :3000 with a
    # broken in-memory state (CLAUDE.md rule 18/29).
    print_info(
        "Dashboard auto-start and recovery are handled by the unified Augur daemon"
    )

    return True


def step_services() -> bool:
    """Step 6: Configure unified background daemon."""
    print_step("Configuring Augur background daemon...")

    if sys.platform != "darwin":
        print_info("Service configuration currently only supported on macOS")
        return True

    repo_root = get_repo_root()

    # Use service_healer for migration and installation
    healer_script = _resolve_daemon_skill_root(repo_root) / "scripts" / "service_healer.py"

    if healer_script.exists():
        # Clean up legacy plists first
        print_info("Cleaning up legacy background services...")
        code, output = run_cmd([sys.executable, str(healer_script), "migrate"])
        if code == 0:
            print_success("Unified Augur daemon installed")
            print_info("All background services now run under 'Augur' in System Settings")
        else:
            print_warning(f"Migration returned code {code}: {output}")
    else:
        print_warning("Service healer not found, manual installation required")
        return False

    return True


def step_ide_bridge() -> bool:
    """Step 7: Setup IDE Bridge for LLM interactions."""
    print_step("Setting up IDE Bridge...")

    if sys.platform != "darwin":
        print_info("IDE Bridge currently only supported on macOS")
        return True

    repo_root = get_repo_root()

    # Paths
    bin_dir = Path.home() / ".augur" / "bin"
    app_path = bin_dir / "Augur Bridge.app"
    bridge_script = repo_root / "src/lib" / "scripts" / "bridge_runner.applescript"
    icon_source = repo_root / "src/lib" / "assets" / "icon.icns"

    # Compile AppleScript app
    print_info("Compiling Augur Bridge app...")
    bin_dir.mkdir(parents=True, exist_ok=True)

    if not bridge_script.exists():
        print_warning(f"AppleScript not found: {bridge_script}")
        return True  # Non-critical

    code, output = run_cmd(["osacompile", "-o", str(app_path), str(bridge_script)])
    if code != 0:
        print_warning(f"Failed to compile bridge app: {output}")
        return True  # Non-critical

    print_success(f"Compiled: {app_path}")

    # Apply icon if available
    if icon_source.exists():
        dest_icon = app_path / "Contents" / "Resources" / "applet.icns"
        if dest_icon.parent.exists():
            code, _ = run_cmd(["cp", str(icon_source), str(dest_icon)])
            if code == 0:
                run_cmd(["touch", str(app_path)])  # Refresh icon cache
                print_success("Applied custom icon")

    # Prompt user to grant accessibility permission
    _out()
    print_info("═" * 50)
    print_info("IMPORTANT: Accessibility Permission Required")
    print_info("═" * 50)
    _out()
    _out("  The Augur Bridge app needs permission to send keystrokes.")
    _out()
    _out("  1. System Settings will open to Accessibility")
    _out(f"  2. Click '+' and add: {app_path}")
    _out("  3. Toggle it ON")
    _out()

    # Ask user if they want to open settings
    try:
        response = input(f"{Colors.CYAN}Open System Settings now? [Y/n]: {Colors.NC}").strip().lower()
        if response != 'n':
            # Open Accessibility settings
            _run_command(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
            _out()
            input(f"{Colors.YELLOW}Press Enter after granting permission...{Colors.NC}")
    except (EOFError, KeyboardInterrupt):
        pass

    print_success("IDE Bridge setup complete")
    return True


def step_cron_jobs() -> bool:
    """Step 8: Setup scheduled cron/nightly jobs."""
    print_step("Setting up scheduled jobs...")

    if sys.platform != "darwin":
        print_info("Scheduled jobs currently only supported on macOS (launchd)")
        return True

    repo_root = get_repo_root()
    data_dir = str(_get_project_root())

    # Paths
    plist_dest = get_launch_agents_dir() / "com.augur.nightly.plist"
    nightly_script = _resolve_daemon_skill_root(repo_root) / "scripts" / "nightly_maintainer.py"
    python_path = sys.executable

    # Log directory
    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / "nightly.out"
    stderr_log = log_dir / "nightly.err"

    if not nightly_script.exists():
        print_warning(f"Nightly script not found: {nightly_script}")
        return True  # Non-critical

    # Generate plist content with correct paths
    plist_content = _render_plist_template(
        "com.augur.nightly.plist.template",
        {
            "__LABEL__": "com.augur.nightly",
            "__PROGRAM__": python_path,
            "__ARG1__": str(nightly_script),
            "__WORKING_DIRECTORY__": str(repo_root),
            "__AUGUR_ROOT__": str(data_dir),
            "__STDOUT__": str(stdout_log),
            "__STDERR__": str(stderr_log),
        },
    )

    try:
        print_info(f"Writing nightly job to {plist_dest}...")
        plist_dest.write_text(plist_content)

        # Unload first if exists
        _run_command(["launchctl", "unload", str(plist_dest)], capture_output=True)

        # Load the job
        code, output = run_cmd(["launchctl", "load", "-w", str(plist_dest)])
        if code != 0:
            print_warning(f"Failed to load nightly job: {output}")
            return True  # Non-critical

        print_success("Nightly job scheduled (runs at 3:00 AM)")
        return True

    except Exception as e:
        print_warning(f"Failed to configure nightly job: {e}")
        return True  # Non-critical


def step_providers() -> bool:
    """Step 9: Configure LLM providers (OAuth, API key, or local Ollama)."""
    print_step("Configuring LLM providers...")
    try:
        from oauth_wizard import run_provider_setup

        return run_provider_setup()
    except ImportError:
        print_warning("Provider setup module not found, skipping")
        return True  # Non-critical
    except KeyboardInterrupt:
        print_info("Provider setup skipped")
        return True


def step_validate() -> bool:
    """Step 10: Validate the setup."""
    print_step("Validating setup...")

    repo_root = get_repo_root()

    checks = [
        (repo_root / ".venv" / "bin" / "python", "Python venv"),
        (repo_root / "scripts" / "augur", "CLI"),
        (repo_root / "plugins", "Packages"),
    ]

    all_ok = True
    for path, name in checks:
        if path.exists():
            print_success(f"{name}: ✓")
        else:
            print_warning(f"{name}: not found")
            all_ok = False

    # Try running CLI list
    print_info("Testing CLI...")
    cli_path = repo_root / "scripts" / "augur"

    if cli_path.exists():
        code, output = run_cmd([str(cli_path), "--list-tools", "--json"])
        if code == 0:
            print_success("CLI working: skills discoverable")
        else:
            print_warning("CLI test failed, but setup may still work")

    return all_ok


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    print_header("🧠 Augur Interactive Setup Wizard")

    _out("This wizard will guide you through setting up Augur.\n")
    _out("Steps:")
    for i, step in enumerate(STEPS, 1):
        _out(f"  {i}. {step}")
    _out()

    step_funcs = [
        step_prerequisites,
        step_ssl_check,
        step_python,
        step_dependencies,
        step_data_dir,
        step_dashboard,
        step_services,
        step_ide_bridge,
        step_providers,
        step_validate,
    ]

    results = []

    for i, (step_name, step_func) in enumerate(zip(STEPS, step_funcs), 1):
        print_progress(i, len(STEPS), step_name)

        try:
            success = step_func()
            results.append((step_name, success))

            if success:
                print_success(f"Completed: {step_name}")
            else:
                print_warning(f"Issues in: {step_name}")
        except Exception as e:
            print_error(f"Error in {step_name}: {e}")
            results.append((step_name, False))

    # Summary
    _out()
    print_header("Setup Summary")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = f"{Colors.GREEN}✓{Colors.NC}" if ok else f"{Colors.YELLOW}⚠{Colors.NC}"
        _out(f"  {status} {name}")

    _out()

    if passed == total:
        print_success(f"All {total} steps completed successfully!")
        _out()
        _out("Next steps:")
        _out("  1. Activate venv: source .venv/bin/activate")
        _out("  2. Start dashboard: cd dashboard && npm run dev")
        _out("  3. Use CLI: ./scripts/augur --list-tools")
    else:
        print_warning(f"{passed}/{total} steps completed. Review warnings above.")

    _out()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
