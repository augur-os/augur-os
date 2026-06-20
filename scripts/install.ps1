#Requires -Version 5.1
<#
.SYNOPSIS
    Augur One-Line Installer for Windows

.DESCRIPTION
    This script installs Augur on Windows systems.

.EXAMPLE
    # Run directly:
    .\install.ps1

    # Or with custom paths:
    $env:AUGUR_DIR = "C:\MyProjects\augur"
    .\install.ps1

    # Install ca/xa/ga/gca PowerShell shortcuts that launch claude/codex/gemini/gh-copilot through Augur launchers:
    .\install.ps1 -InstallCliShortcuts
    # (or set $env:AUGUR_INSTALL_CLI_ALIASES = "1" before invoking)

.NOTES
    Requires: Git, Python 3.11+
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [Alias("TrustSystemCerts")]
    [switch]$CorporateMode,
    [switch]$InstallCliShortcuts
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

# Ensure localhost bypasses proxies
$env:NO_PROXY = "localhost,127.0.0.1,::1"

$REPO_URL = "https://github.com/augur-os/augur-os.git"
$INSTALL_DIR = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
$BRANCH = if ($env:AUGUR_BRANCH) { $env:AUGUR_BRANCH } else { "main" }
$VENV_DIR = ".venv"
$RUN_TESTS = -not $SkipTests
# Allow opting in via env var as well as the -InstallCliShortcuts switch.
if ($env:AUGUR_INSTALL_CLI_ALIASES -eq "1" -or $env:AUGUR_INSTALL_CLI_ALIASES -eq "true") {
    $InstallCliShortcuts = $true
}
$PY_VERSION_MIN = [Version]"3.11.0"
$PY_VERSION_MAX = [Version]"3.15.0"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host ("=" * 55) -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host ("=" * 55) -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "> $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Get-PythonCommand {
    # Try various Python command names
    $commands = @("python", "python3", "py")
    foreach ($cmd in $commands) {
        if (Test-Command $cmd) {
            try {
                $version = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
                if ($version) {
                    $parsedVersion = [Version]$version
                    if ($parsedVersion -ge $PY_VERSION_MIN -and $parsedVersion -lt $PY_VERSION_MAX) {
                        return @{
                            Command = $cmd
                            Version = $version
                        }
                    }
                }
            } catch {
                continue
            }
        }
    }
    return $null
}

function Get-UvCommand {
    $commands = @("uv")
    foreach ($cmd in $commands) {
        if (Test-Command $cmd) {
            try {
                $version = & $cmd --version 2>$null
                return @{
                    Command = $cmd
                    Version = $version
                }
            } catch {
                continue
            }
        }
    }

    $localUv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $localUv) {
        try {
            $version = & $localUv --version 2>$null
            return @{
                Command = $localUv
                Version = $version
            }
        } catch {
            return $null
        }
    }

    return $null
}

function Ensure-Uv {
    $uv = Get-UvCommand
    if ($null -ne $uv) {
        Write-Success "Using $($uv.Version)"
        return $uv
    }

    Write-Warning "uv is not installed. Installing..."
    try {
        Invoke-RestMethod "https://astral.sh/uv/install.ps1" | Invoke-Expression
    } catch {
        Write-Error "Failed to install uv: $_"
        exit 1
    }

    $localBin = Join-Path $env:USERPROFILE ".local\bin"
    if ((Test-Path $localBin) -and -not (($env:PATH -split ";") -contains $localBin)) {
        $env:PATH = "$localBin;$env:PATH"
    }

    $uv = Get-UvCommand
    if ($null -eq $uv) {
        Write-Error "uv installation did not produce an executable on PATH"
        exit 1
    }

    Write-Success "Using $($uv.Version)"
    return $uv
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION MANAGEMENT & NETWORKING
# ═══════════════════════════════════════════════════════════════════════════════

function Get-ExoConfig {
    param($InstallDir)
    $configPath = Join-Path $InstallDir ".agent\config.json"
    if (Test-Path $configPath) {
        try {
            return Get-Content $configPath -Raw | ConvertFrom-Json
        } catch {
            return @{}
        }
    }
    return @{}
}

function Set-ExoConfig {
    param($InstallDir, $Config)
    $agentDir = Join-Path $InstallDir ".agent"
    if (-not (Test-Path $agentDir)) {
        New-Item -ItemType Directory -Path $agentDir -Force | Out-Null
    }
    $configPath = Join-Path $agentDir "config.json"
    $Config | ConvertTo-Json -Depth 5 | Set-Content $configPath
}

function Test-NetworkConnectivity {
    Write-Step "Checking network connectivity..."
    
    try {
        $req = [System.Net.HttpWebRequest]::Create("https://github.com")
        $req.Timeout = 5000
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch {
        if ($_.Exception.Message -match "SSL" -or $_.Exception.InnerException.Message -match "SSL" -or $_.Exception.Message -match "secure channel") {
            Write-Warning "SSL/TLS verification failed. You appear to be behind a corporate proxy."
            return $false
        }
        # If it's another error (timeout etc), we assume it's not a cert issue, but let's be safe.
        # Actually returning $true means "No SSL Error Detected".
        return $true
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# INSTALLATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

function Configure-SSL {
    param(
        [ref]$CorporateModeRef
    )
    
    # 1. Load existing config
    $config = Get-ExoConfig -InstallDir $INSTALL_DIR
    
    # 2. Check Auto-Detection if flag is not explicitly set
    if (-not $CorporateModeRef.Value) {
        if ($config.trust_system_certs) {
            Write-Info "Corporate Mode enabled via config."
            $CorporateModeRef.Value = $true
        } else {
            # Run test
            $sslOk = Test-NetworkConnectivity
            if (-not $sslOk) {
                Write-Warning "Enabling Corporate Mode automatically (Proxy/SSL detected)."
                $CorporateModeRef.Value = $true
                
                # Update config object for saving later
                $config.trust_system_certs = $true
                Set-ExoConfig -InstallDir $INSTALL_DIR -Config $config
            }
        }
    } else {
        # Flag was explicitly passed, save it to config
        $config.trust_system_certs = $true
        Set-ExoConfig -InstallDir $INSTALL_DIR -Config $config
    }

    if ($CorporateModeRef.Value) {
        Write-Step "Configuring environment for corporate network..."
        
        # Configure Git to use Windows Secure Channel (uses system cert store)
        Write-Info "Configuring Git to use Windows Certificate Store..."
        git config --global http.sslBackend schannel
        
        # Configure NPM to disable strict SSL (easier workaround than CA bundle)
        if (Test-Command "npm") {
            Write-Info "Configuring NPM to disable strict SSL..."
            npm config set strict-ssl false
            Write-Success "NPM configured to trust corporate certificates"
        }

        Write-Success "Git configured to use system certificates"

        # PERSISTENT LOCALHOST FIX:
        # If we are in "Corporate Mode", we MUST ensure NO_PROXY is set persistently
        # so that dashboard/scripts work in future sessions.
        $currentNoProxy = [Environment]::GetEnvironmentVariable("NO_PROXY", "User")
        if (-not $currentNoProxy -or $currentNoProxy -notmatch "localhost") {
            Write-Info "Setting persistent NO_PROXY to bypass proxy for localhost..."
            [Environment]::SetEnvironmentVariable("NO_PROXY", "localhost,127.0.0.1,::1", "User")
            # Update current session as well (already done globally, but good for safety)
            $env:NO_PROXY = "localhost,127.0.0.1,::1"
            Write-Success "NO_PROXY configured for user"
        }

        # NEXT.JS / TURBOPACK FIX:
        # Next.js 15+ with Turbopack needs this to use system certs for font fetching etc.
        $currentTurbopack = [Environment]::GetEnvironmentVariable("NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS", "User")
        if ($currentTurbopack -ne "1") {
            Write-Info "Setting NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1..."
            [Environment]::SetEnvironmentVariable("NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS", "1", "User")
            $env:NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS = "1"
            Write-Success "Turbopack SSL workaround applied"
        }
    }
}

function Test-Prerequisites {
    Write-Step "Checking prerequisites..."

    # Check Git
    if (Test-Command "git") {
        Write-Success "Git is installed"
    } else {
        Write-Error "Git is not installed"
        Write-Host ""
        Write-Host "Please install Git for Windows from: https://git-scm.com/download/win"
        Write-Host "Or use: winget install Git.Git"
        exit 1
    }

    # Check Python
    $python = Get-PythonCommand
    if ($null -eq $python) {
        Write-Error "Python $PY_VERSION_MIN+ (< $PY_VERSION_MAX) is required but not found"
        Write-Host ""
        Write-Host "Please install Python from: https://www.python.org/downloads/"
        Write-Host "Or use: winget install Python.Python.3.11"
        Write-Host ""
        Write-Host "IMPORTANT: During installation, check 'Add Python to PATH'"
        exit 1
    }

    Write-Success "Using $($python.Command) ($($python.Version))"
    return $python
}

function Install-SystemDeps {
    Write-Step "Checking OCR system dependencies..."

    $deps = @{
        "tesseract" = "Tesseract OCR"
        "gs" = "Ghostscript"
    }

    $missing = @()
    foreach ($dep in $deps.Keys) {
        if (-not (Test-Command $dep)) {
            $missing += $deps[$dep]
        }
    }

    if ($missing.Count -gt 0) {
        Write-Warning "Optional dependencies not found: $($missing -join ', ')"
        Write-Host ""
        Write-Host "To install OCR dependencies, you can use Chocolatey:" -ForegroundColor Yellow
        Write-Host "  choco install tesseract poppler ghostscript" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Or download manually:" -ForegroundColor Yellow
        Write-Host "  Tesseract: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Gray
        Write-Host "  Ghostscript: https://www.ghostscript.com/releases/gsdnld.html" -ForegroundColor Gray
        Write-Host "  Poppler: https://github.com/oschwartz10612/poppler-windows/releases" -ForegroundColor Gray
        Write-Host ""
        Write-Host "These are optional - the core system will work without them."
    } else {
        Write-Success "OCR dependencies found"
    }
}

function Install-Repository {
    param([hashtable]$Python)

    Write-Step "Setting up repository..."

    if (Test-Path $INSTALL_DIR) {
        if (Test-Path (Join-Path $INSTALL_DIR ".git")) {
            Write-Warning "Directory exists and is a git repository"
            $response = Read-Host "Update existing installation? [Y/n]"
            if ($response -eq "n" -or $response -eq "N") {
                Write-Info "Installation cancelled"
                exit 0
            }

            Write-Step "Updating existing installation..."
            Push-Location $INSTALL_DIR
            try {
                git fetch origin $BRANCH
                git checkout $BRANCH
                git pull origin $BRANCH
                Write-Success "Updated to latest version"
            } finally {
                Pop-Location
            }
        } else {
            Write-Error "Directory exists but is not an Augur repository"
            Write-Host "Please remove it or set AUGUR_DIR to a different location"
            exit 1
        }
    } else {
        Write-Step "Cloning repository..."
        $parentDir = Split-Path $INSTALL_DIR -Parent
        if (-not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        git clone --depth 1 --branch $BRANCH $REPO_URL $INSTALL_DIR
        Write-Success "Repository cloned"
    }
}

function Install-PythonEnvironment {
    param(
        [hashtable]$Python,
        [hashtable]$Uv
    )

    Write-Step "Setting up Python environment with uv..."

    Push-Location $INSTALL_DIR
    try {
        if ($CorporateMode) {
            $env:UV_NATIVE_TLS = "1"
        }

        & $Uv.Command sync --group dev --extra windows --python $Python.Command
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync failed with exit code $LASTEXITCODE"
        }

        Write-Success "Python environment created with uv"
    } finally {
        Pop-Location
    }
}

function New-RuntimeDirectories {
    Write-Step "Creating runtime directory structure..."

    $directories = @(
        "state",
        "logs",
        "ipc",
        "cache",
        ".agent/archive"
    )

    foreach ($dir in $directories) {
        $fullPath = Join-Path $INSTALL_DIR $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        }
    }

    Write-Success "Runtime directories created at $INSTALL_DIR"
}

function Configure-Mcp {
    param([hashtable]$Python)

    Write-Step "Writing MCP config for Cursor..."

    $venvPython = Join-Path (Join-Path $INSTALL_DIR $VENV_DIR) "Scripts\python.exe"

    Push-Location $INSTALL_DIR
    try {
        if (-not (Test-Path $venvPython)) {
            Write-Warning "Repo venv Python not found at $venvPython; skipping Cursor MCP configuration"
            return
        }

        & $venvPython "scripts/configure_mcp.py" --client cursor --auto

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Cursor MCP config updated"
        } else {
            Write-Warning "Cursor MCP configuration exited with code $LASTEXITCODE"
        }
    } catch {
        Write-Warning "Cursor MCP configuration could not be completed: $_"
    } finally {
        Pop-Location
    }
}

function Verify-DocumentUnderstanding {
    param([hashtable]$Uv)

    Write-Step "Verifying document-understanding capability..."

    $pythonCode = @"
import importlib.util
import json
from pathlib import Path

tool_path = Path("project-brain/capabilities/skills/document-extractor/scripts/mcp/tools_extract.py").resolve()
spec = importlib.util.spec_from_file_location("document_extractor_status", tool_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)
print(json.dumps(module.get_extraction_status_impl()))
"@

    Push-Location $INSTALL_DIR
    try {
        $statusJson = & $Uv.Command run python -c $pythonCode
        if ($LASTEXITCODE -ne 0) {
            throw "Document capability check failed with exit code $LASTEXITCODE"
        }

        $status = $statusJson | ConvertFrom-Json
        $documentParsing = if ($status.capabilities.document_parsing_ready) { "OK" } else { "MISSING" }
        $textPdf = if ($status.capabilities.text_pdf_extraction_ready) { "OK" } else { "MISSING" }
        $ocrEnhancement = if ($status.capabilities.ocr_enhancement_ready) { "OK" } else { "Unavailable" }
        $advancedVision = if ($status.capabilities.advanced_vision_ready) { "Optional" } else { "Not installed" }

        Write-Host "  document parsing: $documentParsing" -ForegroundColor Gray
        Write-Host "  text PDF extraction: $textPdf" -ForegroundColor Gray
        Write-Host "  OCR enhancement: $ocrEnhancement" -ForegroundColor Gray
        Write-Host "  advanced vision OCR: $advancedVision" -ForegroundColor Gray
    } catch {
        Write-Warning "Document capability check could not complete: $_"
    } finally {
        Pop-Location
    }
}

function Invoke-Tests {
    param([hashtable]$Uv)

    if (-not $RUN_TESTS) {
        Write-Info "Skipping tests (-SkipTests specified)"
        return
    }

    Write-Step "Running test suite..."

    Push-Location $INSTALL_DIR
    try {
        $env:LOCAL_RAG_REAL_OCR_DEPS = "0"  # Skip OCR tests on Windows initially
        $testPath = "project-brain/capabilities/skills/document-extractor/augur/tests/test_tools_extract.py"
        if (Test-Path (Join-Path $INSTALL_DIR $testPath)) {
            & $Uv.Command run pytest $testPath -q --tb=short
        } else {
            Write-Warning "Document extractor smoke tests not found at $testPath"
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Tests passed"
        } else {
            Write-Warning "Some tests failed (exit code: $LASTEXITCODE)"
        }
    } catch {
        Write-Warning "Tests could not be run: $_"
    } finally {
        Pop-Location
    }
}

function Get-CliAliasProfilePaths {
    $paths = @()

    if ($PROFILE.CurrentUserAllHosts) {
        $paths += $PROFILE.CurrentUserAllHosts
    }
    if ($PROFILE.CurrentUserCurrentHost) {
        $paths += $PROFILE.CurrentUserCurrentHost
    }

    $documentsDir = [Environment]::GetFolderPath("MyDocuments")
    if ($documentsDir) {
        $paths += (Join-Path (Join-Path $documentsDir "PowerShell") "profile.ps1")
        $paths += (Join-Path (Join-Path $documentsDir "PowerShell") "Microsoft.PowerShell_profile.ps1")
        $paths += (Join-Path (Join-Path $documentsDir "WindowsPowerShell") "profile.ps1")
        $paths += (Join-Path (Join-Path $documentsDir "WindowsPowerShell") "Microsoft.PowerShell_profile.ps1")
    }

    $paths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
}

function Install-CliAliases {
    Write-Step "Installing CLI shortcuts (ca/xa/ga/gca) into PowerShell profiles..."

    $beginMarker = "# === augur CLI shortcuts (ca/xa/ga) ==="
    $endMarker = "# === end augur CLI shortcuts ==="
    $installDirLiteral = $INSTALL_DIR.Replace("'", "''")
    $block = @"

$beginMarker
# Launches Claude / Codex / Gemini / GitHub Copilot CLI through Augur's native main/worktree launchers.
# Use "xa --desktop" to open this repo in Codex Desktop for browser-capable sessions.
`$AugurInstallDir = '$installDirLiteral'
`$caLauncher = Join-Path `$AugurInstallDir "scripts\ca-launch.ps1"
`$xaLauncher = Join-Path `$AugurInstallDir "scripts\xa-launch.ps1"
`$gaLauncher = Join-Path `$AugurInstallDir "scripts\ga-launch.ps1"
`$gcaLauncher = Join-Path `$AugurInstallDir "scripts\gca-launch.ps1"
function ca { & `$caLauncher @args }
function xa { & `$xaLauncher @args }
function ga { & `$gaLauncher @args }
function gca { & `$gcaLauncher @args }
$endMarker
"@

    $replacementBlock = $block.Trim()
    $existingBlockPattern = "(?s)$([regex]::Escape($beginMarker)).*?$([regex]::Escape($endMarker))"
    foreach ($profilePath in Get-CliAliasProfilePaths) {
        $profileDir = Split-Path $profilePath -Parent
        if (-not (Test-Path $profileDir)) {
            New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
        }

        if (Test-Path $profilePath) {
            $content = Get-Content -Path $profilePath -Raw
            if ($content -match [regex]::Escape($beginMarker)) {
                $updated = [regex]::Replace($content, $existingBlockPattern, $replacementBlock, 1)
                Set-Content -Path $profilePath -Value $updated -Encoding UTF8
                Write-Success "Updated ca/xa/ga/gca aliases in $profilePath"
                continue
            }
        }

        foreach ($launcher in @("scripts\ca-launch.ps1", "scripts\xa-launch.ps1", "scripts\ga-launch.ps1", "scripts\gca-launch.ps1")) {
            $launcherPath = Join-Path $INSTALL_DIR $launcher
            if (-not (Test-Path $launcherPath)) {
                Write-Warning "Expected launcher not found: $launcherPath"
            }
        }

        if ((Test-Path $profilePath) -and ((Get-Content -Path $profilePath -Raw).Trim().Length -gt 0)) {
            Add-Content -Path $profilePath -Value $block -Encoding UTF8
        } else {
            Set-Content -Path $profilePath -Value $replacementBlock -Encoding UTF8
        }
        Write-Success "Added ca/xa/ga/gca aliases to $profilePath"
    }

    Write-Info "Open a new PowerShell window or reload the updated profile to load them now"
}

function Show-Completion {
    Write-Header "Installation Complete!"

    Write-Host "Next steps:" -ForegroundColor White
    Write-Host ""
    Write-Host "  Get to know your AI setup, build your local second brain, and talk with your projects." -ForegroundColor White
    Write-Host ""
    Write-Host "  1. Fast launch next step: choose a folder and run:" -ForegroundColor Gray
    Write-Host "     Which folder should I initialize?" -ForegroundColor White
    Write-Host "     Set-Location `"$INSTALL_DIR`"; uv run aug init --project <folder>" -ForegroundColor Cyan
    Write-Host "     This creates or attaches project-brain/ and writes the read-only AI artifact inventory." -ForegroundColor DarkGray
    Write-Host "     Report Browse: http://localhost:3000/browse" -ForegroundColor DarkGray
    Write-Host "     Next action: Ask Augur about this project." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  2. Contributor validation:" -ForegroundColor Gray
    Write-Host "     Use the managed dev workflow when you need the dashboard." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  3. Activate the virtual environment when you need shell access:" -ForegroundColor Gray
    Write-Host "     $INSTALL_DIR\$VENV_DIR\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  4. Review MCP clients or re-run configuration:" -ForegroundColor Gray
    Write-Host "     python scripts/configure_mcp.py --list-ides" -ForegroundColor Cyan
    Write-Host "     python scripts/configure_mcp.py --client cursor --auto" -ForegroundColor Cyan
    Write-Host ""
    if ($InstallCliShortcuts) {
        Write-Host "  5. CLI shortcuts installed in your PowerShell profile:" -ForegroundColor Gray
        Write-Host "     ca   -> Augur Claude launcher (main/worktree prompt)" -ForegroundColor Cyan
        Write-Host "     xa   -> Augur Codex launcher (main/worktree prompt)" -ForegroundColor Cyan
        Write-Host "     xa --desktop -> open Augur in Codex Desktop for browser-capable sessions" -ForegroundColor Cyan
        Write-Host "     ga   -> Augur Gemini launcher (main/worktree prompt)" -ForegroundColor Cyan
        Write-Host "     gca  -> Augur GitHub Copilot CLI launcher (main/worktree prompt)" -ForegroundColor Cyan
        Write-Host "     (open a new shell or reload the updated profile to load)" -ForegroundColor DarkGray
        Write-Host ""
    } else {
        Write-Host "  5. Optional: install CLI shortcuts (ca/xa/ga/gca) for claude/codex/gemini/gh-copilot" -ForegroundColor Gray
        Write-Host "     through Augur's main/worktree launchers by re-running with -InstallCliShortcuts" -ForegroundColor DarkGray
        Write-Host "     xa also supports --desktop after shortcuts are installed" -ForegroundColor DarkGray
        Write-Host ""
    }
    Write-Host "Skills live in: $INSTALL_DIR\project-brain\capabilities\skills\" -ForegroundColor White
    Write-Host "User data lives in: ~\Vault\Augur\" -ForegroundColor White
    Write-Host ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

function Main {
    Write-Header "Augur Installer for Windows"

    Write-Host "This script will:"
    Write-Host "  1. Check prerequisites (Git, Python 3.11+, uv)"
    Write-Host "  2. Clone or update the Augur repository"
    Write-Host "  3. Check for OCR dependencies (optional)"
    Write-Host "  4. Create the Python environment with uv"
    Write-Host "  5. Verify document-understanding capability"
    Write-Host "  6. Create runtime directories"
    Write-Host "  7. Run tests (use -SkipTests to skip)"
    if ($InstallCliShortcuts) {
        Write-Host "  8. Install CLI shortcuts (ca/xa/ga/gca) into PowerShell profile"
    } else {
        Write-Host "     (CLI shortcuts ca/xa/ga/gca: opt in with -InstallCliShortcuts)" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Installation directory: $INSTALL_DIR" -ForegroundColor Cyan
    Write-Host ""

    Configure-SSL -CorporateModeRef ([ref]$CorporateMode)
    $python = Test-Prerequisites
    $uv = Ensure-Uv
    Install-Repository -Python $python
    Install-PythonEnvironment -Python $python -Uv $uv
    Install-SystemDeps
    Verify-DocumentUnderstanding -Uv $uv
    New-RuntimeDirectories
    Configure-Mcp -Python $python
    Invoke-Tests -Uv $uv
    if ($InstallCliShortcuts) {
        Install-CliAliases
    }
    Show-Completion
}

# Run main only if not dot-sourced
if ($MyInvocation.InvocationName -ne '.') {
    try {
        Main
    } catch {
        Write-Error "Installation failed: $_"
        Write-Host $_.ScriptStackTrace -ForegroundColor Gray
        exit 1
    }
}
