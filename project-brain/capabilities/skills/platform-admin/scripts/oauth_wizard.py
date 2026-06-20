#!/usr/bin/env python3
"""
OAuth & Provider Setup Wizard for Augur.

Interactive CLI that lets users authenticate with LLM providers via:
  - OAuth (Glama, OpenRouter) — one-click browser-based auth
  - Manual API key (Anthropic, OpenAI, Gemini, Groq, Together, Custom)
  - Local LLM (Ollama) — no key needed

Standalone usage:
    python3 project-brain/capabilities/skills/platform-admin/scripts/oauth_wizard.py

Configure a specific provider:
    python3 project-brain/capabilities/skills/platform-admin/scripts/oauth_wizard.py --provider glama

List configured providers:
    python3 project-brain/capabilities/skills/platform-admin/scripts/oauth_wizard.py --list

Verify a provider:
    python3 project-brain/capabilities/skills/platform-admin/scripts/oauth_wizard.py --verify glama

From setup_wizard.py:
    from oauth_wizard import run_provider_setup
    success = run_provider_setup()
"""

from __future__ import annotations

import argparse
import getpass
import sys
import webbrowser
from pathlib import Path

if __package__ in {None, ""}:
    # Standalone script execution: bootstrap the project root and use local lib package.
    from bootstrap_paths import ensure_project_paths

    ensure_project_paths(__file__)
    from lib.callback_server import OAuthCallbackServer
    from lib.credential_store import CredentialStore
    from lib.oauth_pkce import (
        build_authorization_url,
        exchange_code,
        generate_code_challenge,
        generate_code_verifier,
        generate_state,
    )
    from lib.ollama_checker import OllamaChecker
    from lib.provider_registry import (
        PROVIDER_REGISTRY,
        get_local_providers,
        get_manual_providers,
        get_oauth_providers,
    )
    from lib.provider_verifier import verify_provider
else:
    from .lib.callback_server import OAuthCallbackServer
    from .lib.credential_store import CredentialStore
    from .lib.oauth_pkce import (
        build_authorization_url,
        exchange_code,
        generate_code_challenge,
        generate_code_verifier,
        generate_state,
    )
    from .lib.ollama_checker import OllamaChecker
    from .lib.provider_registry import (
        PROVIDER_REGISTRY,
        get_local_providers,
        get_manual_providers,
        get_oauth_providers,
    )
    from .lib.provider_verifier import verify_provider

# =============================================================================
# Colors (matches setup_wizard.py pattern)
# =============================================================================


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        for attr in ("RED", "GREEN", "YELLOW", "BLUE", "CYAN", "MAGENTA", "BOLD", "DIM", "NC"):
            setattr(cls, attr, "")


# Disable colors if not a terminal
if not sys.stdout.isatty():
    Colors.disable()


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    sys.stdout.write(str(sep).join(str(a) for a in args) + str(end))
    sys.stdout.flush()


def print_header(text: str) -> None:
    _out(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 55}{Colors.NC}")
    _out(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.NC}")
    _out(f"{Colors.BOLD}{Colors.CYAN}{'=' * 55}{Colors.NC}\n")


def print_success(text: str) -> None:
    _out(f"  {Colors.GREEN}\u2713 {text}{Colors.NC}")


def print_error(text: str) -> None:
    _out(f"  {Colors.RED}\u2717 {text}{Colors.NC}")


def print_warning(text: str) -> None:
    _out(f"  {Colors.YELLOW}\u26a0 {text}{Colors.NC}")


def print_info(text: str) -> None:
    _out(f"  {Colors.CYAN}\u2139 {text}{Colors.NC}")


def print_step(text: str) -> None:
    _out(f"  {Colors.BOLD}{Colors.BLUE}\u25b6 {text}{Colors.NC}")


# =============================================================================
# Provider Flows
# =============================================================================


def _oauth_flow(provider_id: str, store: CredentialStore) -> bool:
    """
    Run the OAuth PKCE flow for a provider.

    Opens browser -> receives callback -> exchanges code -> stores key.
    """
    provider = PROVIDER_REGISTRY[provider_id]
    print_step(f"Starting OAuth for {provider.name}...")

    # 1. Generate PKCE parameters
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = generate_state()

    # 2. Start callback server
    try:
        server = OAuthCallbackServer()
        callback_url = server.start()
    except RuntimeError as e:
        print_error(f"Could not start callback server: {e}")
        return False

    # 3. Build auth URL and open browser
    auth_url = build_authorization_url(provider_id, code_challenge, state, callback_url)

    _out(f"\n  Opening browser for {Colors.BOLD}{provider.name}{Colors.NC} authentication...")
    _out(f"  {Colors.DIM}If browser doesn't open, visit:{Colors.NC}")
    _out(f"  {Colors.CYAN}{auth_url}{Colors.NC}\n")

    webbrowser.open(auth_url)

    # 4. Wait for callback
    _out("  Waiting for authentication (5 min timeout)...")
    try:
        code, returned_state = server.wait_for_callback()
    except TimeoutError:
        print_error("Authentication timed out. Please try again.")
        server.stop()
        return False
    except RuntimeError as e:
        print_error(str(e))
        server.stop()
        return False
    finally:
        server.stop()

    # 5. Validate CSRF state
    if returned_state and returned_state != state:
        print_error("State mismatch — possible CSRF attack. Aborting.")
        return False

    if not code:
        print_error("No authorization code received.")
        return False

    # 6. Exchange code for API key
    _out("  Exchanging code for API key...")
    api_key, error = exchange_code(provider_id, code, code_verifier)
    if error:
        print_error(f"Code exchange failed: {error}")
        return False

    # 7. Store key
    store.store_key(provider_id, api_key)
    store.update_remote_providers(provider_id, has_key=True, is_oauth=True)
    store.update_llm_yaml(provider_id)

    # 8. Verify
    success, msg = verify_provider(provider_id, api_key)
    if success:
        print_success(msg)
    else:
        print_warning(f"Key stored but verification failed: {msg}")

    return True


def _manual_key_flow(provider_id: str, store: CredentialStore) -> bool:
    """
    Prompt user for an API key and store it.
    """
    provider = PROVIDER_REGISTRY[provider_id]

    _out(f"\n  {Colors.BOLD}{provider.name}{Colors.NC}: {provider.description}")
    if provider.website_url:
        _out(f"  Get your API key at: {Colors.CYAN}{provider.website_url}{Colors.NC}")

    # Custom provider needs extra info
    custom_base_url = ""

    if provider_id == "custom":
        _out("")
        custom_base_url = input("  Enter base URL (e.g., http://localhost:8080/v1): ").strip()
        _ = input("  Enter default model name: ").strip()
        if not custom_base_url:
            print_error("Base URL is required for custom providers.")
            return False

    # Prompt for API key (masked)
    _out("")
    api_key = getpass.getpass("  Enter API key (hidden): ").strip()
    if not api_key:
        print_error("API key cannot be empty.")
        return False

    # Verify
    _out("  Verifying key...")
    success, msg = verify_provider(provider_id, api_key)
    if success:
        print_success(msg)
    else:
        print_warning(f"Verification failed: {msg}")
        try:
            confirm = input("  Store key anyway? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _out("")
            return False
        if confirm != "y":
            print_info("Key not stored.")
            return False

    # Store
    store.store_key(provider_id, api_key)
    store.update_remote_providers(provider_id, has_key=True, is_oauth=False)
    store.update_llm_yaml(provider_id)
    print_success(f"{provider.name} configured successfully.")
    return True


def _ollama_flow(store: CredentialStore) -> bool:
    """
    Check Ollama installation, help set up if needed, update config.
    """
    checker = OllamaChecker()

    _out(f"\n  {Colors.BOLD}Ollama (Local LLM){Colors.NC}: Run models locally — no API key needed")

    # 1. Check installation
    if not checker.is_installed():
        print_warning("Ollama is not installed.")
        _out(f"\n  {checker.install_instructions()}\n")
        try:
            install = input("  Install now? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _out("")
            return False
        if install not in ("n", "no"):
            _out("  Installing Ollama (this may take a minute)...")
            if checker.try_install():
                print_success("Ollama installed.")
            else:
                print_error("Installation failed. Please install manually.")
                return False
        else:
            print_info("Skipped Ollama installation.")
            return False

    # Re-check after possible install
    if not checker.is_installed():
        print_error("Ollama binary not found on PATH.")
        return False

    # 2. Check if running
    if not checker.is_running():
        print_warning("Ollama is installed but not running.")
        try:
            start = input("  Start Ollama server? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _out("")
            return False
        if start not in ("n", "no"):
            _out("  Starting Ollama server...")
            if checker.try_start():
                print_success("Ollama server started.")
            else:
                print_error("Could not start Ollama. Run manually: ollama serve")
                return False

    # 3. Check models
    models = checker.get_models()
    if models:
        _out(f"  Models installed: {Colors.CYAN}{', '.join(models[:5])}{Colors.NC}")
    else:
        print_warning("No models installed.")
        try:
            pull = input("  Pull llama3.2 (recommended, ~2GB)? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _out("")
            return False
        if pull not in ("n", "no"):
            _out("  Pulling llama3.2 (this may take several minutes)...")
            if checker.pull_model("llama3.2"):
                print_success("Model llama3.2 downloaded.")
            else:
                print_error("Model pull failed. Run manually: ollama pull llama3.2")

    # 4. Update config
    store.update_llm_yaml("ollama")

    # 5. Verify
    success, msg = verify_provider("ollama")
    if success:
        print_success(msg)
    else:
        print_warning(msg)

    return True


# =============================================================================
# Interactive Menu
# =============================================================================


def _show_status(store: CredentialStore) -> None:
    """Show current provider configuration status."""
    configured = store.get_configured_providers()

    _out(f"\n  {Colors.BOLD}Current status:{Colors.NC}")
    for pid, provider in PROVIDER_REGISTRY.items():
        if pid == "ollama":
            is_ok = store.is_configured("ollama")
        else:
            is_ok = pid in configured

        icon = f"{Colors.GREEN}\u2713{Colors.NC}" if is_ok else f"{Colors.DIM}\u2717{Colors.NC}"
        name = f"{Colors.BOLD}{provider.name}{Colors.NC}" if is_ok else f"{Colors.DIM}{provider.name}{Colors.NC}"
        method = ""
        if is_ok:
            if provider.auth_method == "oauth":
                method = f" {Colors.DIM}(OAuth){Colors.NC}"
            elif provider.auth_method == "local":
                checker = OllamaChecker()
                models = checker.get_models()
                method = f" {Colors.DIM}({len(models)} models){Colors.NC}" if models else ""
        _out(f"    {icon} {name}{method}")
    _out("")


def _show_menu() -> None:
    """Display the provider selection menu."""
    _out(f"  {Colors.BOLD}Select a provider to configure:{Colors.NC}\n")

    # OAuth providers
    _out(f"  {Colors.MAGENTA}[OAuth — One Click]{Colors.NC}")
    oauth = get_oauth_providers()
    for i, p in enumerate(oauth, 1):
        rec = f" {Colors.GREEN}(RECOMMENDED){Colors.NC}" if p.id == "glama" else ""
        _out(f"    {Colors.BOLD}{i}.{Colors.NC} {p.name:<14s} {Colors.DIM}{p.description}{Colors.NC}{rec}")

    # Manual providers
    _out(f"\n  {Colors.MAGENTA}[API Key — Manual]{Colors.NC}")
    manual = get_manual_providers()
    offset = len(oauth) + 1
    for i, p in enumerate(manual, offset):
        _out(f"    {Colors.BOLD}{i}.{Colors.NC} {p.name:<14s} {Colors.DIM}{p.description}{Colors.NC}")

    # Local
    _out(f"\n  {Colors.MAGENTA}[Local]{Colors.NC}")
    local = get_local_providers()
    local_offset = offset + len(manual)
    for i, p in enumerate(local, local_offset):
        _out(f"    {Colors.BOLD}{i}.{Colors.NC} {p.name:<14s} {Colors.DIM}{p.description}{Colors.NC}")

    _out(f"\n    {Colors.BOLD}0.{Colors.NC} Done\n")


# Ordered menu mapping: number -> provider_id
_MENU_ORDER = [
    # OAuth
    "glama",
    "openrouter",
    # Manual
    "anthropic",
    "openai",
    "gemini",
    "groq",
    "together",
    "custom",
    # Local
    "ollama",
]


def run_provider_setup() -> bool:
    """
    Main entry point — interactive provider setup menu.

    Callable from setup_wizard.py or standalone.
    Returns True if at least one provider was configured.
    """
    store = CredentialStore()
    configured_any = False

    print_header("Augur LLM Provider Setup")

    while True:
        _show_status(store)
        _show_menu()

        try:
            choice_str = input(f"  Choice [0-{len(_MENU_ORDER)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            _out("")
            break

        if not choice_str or choice_str == "0":
            break

        try:
            choice = int(choice_str)
        except ValueError:
            print_error("Please enter a number.")
            continue

        if choice < 1 or choice > len(_MENU_ORDER):
            print_error(f"Please enter 0-{len(_MENU_ORDER)}.")
            continue

        provider_id = _MENU_ORDER[choice - 1]
        provider = PROVIDER_REGISTRY[provider_id]

        success = False
        if provider.auth_method == "oauth":
            success = _oauth_flow(provider_id, store)
        elif provider.auth_method == "manual":
            success = _manual_key_flow(provider_id, store)
        elif provider.auth_method == "local":
            success = _ollama_flow(store)

        if success:
            configured_any = True

        _out("")  # Spacing before next menu

    if configured_any:
        print_success("Provider setup complete!")
    else:
        print_info("No providers configured. You can run this wizard again anytime.")

    return configured_any


# =============================================================================
# CLI Commands
# =============================================================================


def _cmd_list(store: CredentialStore) -> None:
    """List configured providers."""
    print_header("Configured Providers")
    configured = store.get_configured_providers()
    if not configured:
        print_info("No providers configured yet.")
        print_info("Run without arguments for interactive setup.")
        return

    for pid in configured:
        provider = PROVIDER_REGISTRY.get(pid)
        if provider:
            print_success(f"{provider.name} ({provider.auth_method})")

    # Check Ollama separately
    if store.is_configured("ollama"):
        checker = OllamaChecker()
        models = checker.get_models()
        suffix = f" — {len(models)} models" if models else ""
        print_success(f"Ollama (local){suffix}")


def _cmd_verify(store: CredentialStore, provider_id: str) -> None:
    """Verify a provider connection."""
    provider = PROVIDER_REGISTRY.get(provider_id)
    if not provider:
        print_error(f"Unknown provider: {provider_id}")
        print_info(f"Available: {', '.join(PROVIDER_REGISTRY.keys())}")
        return

    print_step(f"Verifying {provider.name}...")
    keys = store.load_keys()
    api_key = keys.get(provider_id, "")

    if not api_key and provider_id != "ollama":
        print_error(f"{provider.name} is not configured. Run setup first.")
        return

    success, msg = verify_provider(provider_id, api_key)
    if success:
        print_success(msg)
    else:
        print_error(msg)


def _cmd_provider(store: CredentialStore, provider_id: str) -> None:
    """Configure a specific provider non-interactively."""
    provider = PROVIDER_REGISTRY.get(provider_id)
    if not provider:
        print_error(f"Unknown provider: {provider_id}")
        print_info(f"Available: {', '.join(PROVIDER_REGISTRY.keys())}")
        return

    print_header(f"Configure {provider.name}")

    if provider.auth_method == "oauth":
        _oauth_flow(provider_id, store)
    elif provider.auth_method == "manual":
        _manual_key_flow(provider_id, store)
    elif provider.auth_method == "local":
        _ollama_flow(store)


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Augur LLM Provider Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s                    # Interactive menu\n"
            "  %(prog)s --provider glama   # Configure Glama via OAuth\n"
            "  %(prog)s --list             # Show configured providers\n"
            "  %(prog)s --verify anthropic # Test Anthropic connection\n"
        ),
    )
    parser.add_argument(
        "--provider",
        metavar="ID",
        help="Configure a specific provider (glama, openrouter, anthropic, etc.)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured providers",
    )
    parser.add_argument(
        "--verify",
        metavar="ID",
        help="Verify a provider connection",
    )
    args = parser.parse_args()

    store = CredentialStore()

    try:
        if args.list:
            _cmd_list(store)
        elif args.verify:
            _cmd_verify(store, args.verify)
        elif args.provider:
            _cmd_provider(store, args.provider)
        else:
            run_provider_setup()
    except KeyboardInterrupt:
        _out(f"\n{Colors.DIM}  Interrupted.{Colors.NC}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
