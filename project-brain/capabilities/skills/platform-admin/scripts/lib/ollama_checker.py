"""
Ollama Checker — Detect, verify, and assist with Ollama local LLM setup.
"""

from __future__ import annotations

import platform
import shutil
import subprocess

import requests

# =============================================================================
# Ollama Checker
# =============================================================================


class OllamaChecker:
    """Check Ollama installation status and help with setup."""

    def is_installed(self) -> bool:
        """Check if the ollama binary is on PATH."""
        return shutil.which("ollama") is not None

    def is_running(self) -> bool:
        """Check if the Ollama server is responding."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            return resp.ok
        except (requests.ConnectionError, requests.Timeout):
            return False

    def get_models(self) -> list[str]:
        """Get list of installed model names."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.ok:
                data = resp.json()
                return [m.get("name", "?") for m in data.get("models", [])]
        except (requests.ConnectionError, requests.Timeout):
            pass
        return []

    def install_instructions(self) -> str:
        """Return platform-appropriate install instructions."""
        system = platform.system().lower()
        if system == "darwin":
            return (
                "Install Ollama:\n"
                "  Option 1: brew install ollama\n"
                "  Option 2: Download from https://ollama.ai/download"
            )
        if system == "linux":
            return "Install Ollama:\n" "  curl -fsSL https://ollama.ai/install.sh | sh"
        return "Install Ollama:\n" "  Download from https://ollama.ai/download"

    def try_install(self) -> bool:
        """
        Attempt to install Ollama using the platform package manager.

        Returns True if install command ran successfully.
        """
        system = platform.system().lower()
        try:
            if system == "darwin" and shutil.which("brew"):
                result = subprocess.run(
                    ["brew", "install", "ollama"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0
            if system == "linux":
                result = subprocess.run(
                    ["sh", "-c", "curl -fsSL https://ollama.ai/install.sh | sh"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            pass
        return False

    def try_start(self) -> bool:
        """
        Attempt to start the Ollama server in the background.

        Returns True if the server starts responding.
        """
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for startup
            import time

            for _ in range(10):
                time.sleep(1)
                if self.is_running():
                    return True
        except OSError:
            pass
        return False

    def pull_model(self, model: str = "llama3.2") -> bool:
        """
        Pull a model. Streams output to terminal.

        Returns True if pull succeeds.
        """
        try:
            result = subprocess.run(
                ["ollama", "pull", model],
                timeout=600,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def default_model(self) -> str:
        """
        Return a sensible default model.

        If models are already installed, return the first one.
        Otherwise suggest llama3.2.
        """
        models = self.get_models()
        if models:
            return models[0]
        return "llama3.2:3b-instruct-q8_0"
