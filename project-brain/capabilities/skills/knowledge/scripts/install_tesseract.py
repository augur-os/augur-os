#!/usr/bin/env python3
"""
Tesseract OCR Installation Script

Automatically detects OS and installs Tesseract with additional language support.
"""

import platform
import shutil
import sys
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run  # nosec B404


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
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
    """Run command with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


class TesseractInstaller:
    """Cross-platform Tesseract installer"""

    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()

    def is_installed(self) -> bool:
        """Check if Tesseract is already installed"""
        try:
            result = _run_command(["tesseract", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                _out(f"✓ Tesseract is installed: {result.stdout.split()[1]}")
                return True
        except (FileNotFoundError, TimeoutExpired):
            pass
        return False

    def check_language_support(self) -> bool:
        """Check if additional language packs are installed"""
        try:
            result = _run_command(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=5)
            langs = result.stdout
            has_heb = "heb" in langs
            has_eng = "eng" in langs

            if has_heb and has_eng:
                _out("✓ English (eng) and additional language packs installed")
                return True
            elif has_eng:
                _out("⚠ English (eng) installed, but additional language packs missing")
                return False
            else:
                _out("⚠ Language packs missing")
                return False

        except (FileNotFoundError, TimeoutExpired):
            return False

    def install_macos(self):
        """Install Tesseract on macOS using Homebrew"""
        _out("Installing Tesseract on macOS...")

        # Check if Homebrew is installed
        try:
            _run_command(["brew", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, CalledProcessError):
            _out("Error: Homebrew is not installed.")
            _out("Install Homebrew first: https://brew.sh")
            return False

        try:
            _out("Installing tesseract...")
            _run_command(["brew", "install", "tesseract"], check=True)

            _out("Installing tesseract language packs...")
            _run_command(["brew", "install", "tesseract-lang"], check=True)

            _out("Installing poppler (PDF support)...")
            _run_command(["brew", "install", "poppler"], check=True)

            _out("✓ Tesseract installation complete!")
            return True

        except CalledProcessError as e:
            _out(f"Error during installation: {e}")
            return False

    def install_linux(self):
        """Install Tesseract on Linux (Ubuntu/Debian)"""
        _out("Installing Tesseract on Linux...")

        # Detect package manager
        has_apt = Path("/usr/bin/apt-get").exists()
        has_yum = Path("/usr/bin/yum").exists()

        if has_apt:
            return self._install_apt()
        elif has_yum:
            return self._install_yum()
        else:
            _out("Error: Unsupported Linux distribution.")
            _out("Please install manually:")
            _out("  - tesseract-ocr")
            _out("  - tesseract-ocr-eng")
            _out("  - tesseract-ocr-heb  (optional, for RTL language OCR support)")
            _out("  - poppler-utils")
            return False

    def _install_apt(self):
        """Install using apt-get (Ubuntu/Debian)"""
        try:
            _out("Updating package list...")
            _run_command(["sudo", "apt-get", "update"], check=True)

            _out("Installing tesseract-ocr...")
            _run_command(
                [
                    "sudo",
                    "apt-get",
                    "install",
                    "-y",
                    "tesseract-ocr",
                    "tesseract-ocr-eng",
                    "tesseract-ocr-heb",
                    "poppler-utils",
                ],
                check=True,
            )

            _out("✓ Tesseract installation complete!")
            return True

        except CalledProcessError as e:
            _out(f"Error during installation: {e}")
            return False

    def _install_yum(self):
        """Install using yum (RHEL/CentOS)"""
        try:
            _out("Installing tesseract...")
            _run_command(
                [
                    "sudo",
                    "yum",
                    "install",
                    "-y",
                    "tesseract",
                    "tesseract-langpack-eng",
                    "tesseract-langpack-heb",
                    "poppler-utils",
                ],
                check=True,
            )

            _out("✓ Tesseract installation complete!")
            return True

        except CalledProcessError as e:
            _out(f"Error during installation: {e}")
            return False

    def install_windows(self):
        """Install Tesseract on Windows"""
        _out("Windows detected. Tesseract installation requires manual steps:")
        _out()
        _out("Option 1: Use WSL (Recommended)")
        _out("  1. Install WSL: wsl --install")
        _out("  2. Run this script inside WSL")
        _out()
        _out("Option 2: Manual Installation")
        _out("  1. Download installer from:")
        _out("     https://github.com/UB-Mannheim/tesseract/wiki")
        _out("  2. Install Tesseract-OCR")
        _out("  3. Add to PATH: C:\\Program Files\\Tesseract-OCR")  # audit-ignore: Windows instruction
        _out("  4. Install language packs (eng required, others optional)")
        _out()
        return False

    def install(self):
        """Install Tesseract for the detected OS"""
        _out("=" * 60)
        _out("Tesseract OCR Installation")
        _out("=" * 60)
        _out(f"Detected OS: {self.system} ({self.machine})")
        _out()

        # Check if already installed
        if self.is_installed():
            if self.check_language_support():
                _out("\n✓ Tesseract is already fully installed with language support!")
                return True
            else:
                _out("\n⚠ Tesseract is installed, but additional language packs are missing.")
                _out("Installing language packs...")

        # Install based on OS
        if self.system == "Darwin":
            success = self.install_macos()
        elif self.system == "Linux":
            success = self.install_linux()
        elif self.system == "Windows":
            success = self.install_windows()
        else:
            _out(f"Error: Unsupported operating system: {self.system}")
            return False

        # Verify installation
        if success:
            _out("\nVerifying installation...")
            if self.is_installed() and self.check_language_support():
                _out("\n✓ Tesseract installation successful!")
                _out("\nTest with: tesseract --list-langs")
                return True
            else:
                _out("\n⚠ Installation completed, but verification failed.")
                return False
        else:
            return False

    def verify_python_plugins(self):
        """Verify required Python plugins are installed"""
        _out("\nChecking Python plugins...")

        required_plugins = {"pytesseract": "pytesseract", "pdf2image": "pdf2image", "pypdf": "pypdf", "PIL": "Pillow"}

        missing = []

        for import_name, package_name in required_plugins.items():
            try:
                __import__(import_name)
                _out(f"  ✓ {package_name}")
            except ImportError:
                _out(f"  ✗ {package_name} (missing)")
                missing.append(package_name)

        if missing:
            _out("\nInstall missing plugins with:")
            _out(f"  pip install {' '.join(missing)}")
            return False

        _out("\n✓ All Python plugins installed!")
        return True


def main():
    """Main installation function"""
    installer = TesseractInstaller()

    # Install Tesseract
    success = installer.install()

    # Check Python plugins
    if success:
        installer.verify_python_plugins()

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
