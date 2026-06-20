#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallDir = $(if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\Augur" }),
    [string]$RepoUrl = $(if ($env:AUGUR_REPO_URL) { $env:AUGUR_REPO_URL } else { "https://github.com/augur-os/augur-os.git" }),
    [string]$Branch = $(if ($env:AUGUR_BRANCH) { $env:AUGUR_BRANCH } else { "main" }),
    [string]$VaultRepo = $(if ($env:AUGUR_VAULT_REPO) { $env:AUGUR_VAULT_REPO } else { "" }),
    [string]$VaultDir = $(if ($env:AUGUR_VAULT) { $env:AUGUR_VAULT } else { "" }),
    [switch]$InitLocalVault,
    [switch]$NoVaultPrompt,
    [switch]$DryRun,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

$StateDir = Join-Path $env:LOCALAPPDATA "Augur\setup"
$StatePath = Join-Path $StateDir "bootstrap-state.json"
$LogPath = Join-Path $StateDir "bootstrap.log"

function Write-Log {
    param([string]$Message)

    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Read-State {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $state = [ordered]@{}

    if (Test-Path $StatePath) {
        try {
            $raw = Get-Content -Path $StatePath -Raw -Encoding UTF8
            if ($raw.Trim().Length -gt 0) {
                $existing = $raw | ConvertFrom-Json
                foreach ($property in $existing.PSObject.Properties) {
                    $state[$property.Name] = $property.Value
                }
            }
        }
        catch {
            Write-Log "Ignoring unreadable setup state: $($_.Exception.Message)"
        }
    }

    return $state
}

function Write-State {
    param(
        [hashtable]$Updates,
        [string[]]$ClearKeys = @()
    )

    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $state = Read-State

    foreach ($key in $ClearKeys) {
        if ($state.Contains($key)) {
            $state.Remove($key)
        }
    }

    foreach ($key in $Updates.Keys) {
        $state[$key] = $Updates[$key]
    }

    $state["updated_at"] = (Get-Date).ToUniversalTime().ToString("o")
    $state | ConvertTo-Json -Depth 8 | Set-Content -Path $StatePath -Encoding UTF8
}

function Get-StateValue {
    param([string]$Key)

    $state = Read-State
    if ($state.Contains($Key)) {
        return $state[$Key]
    }

    return $null
}

function Test-CommandAvailable {
    param([string]$Name)

    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    foreach ($candidate in @("python", "python3")) {
        $commands = @(Get-Command $candidate -All -ErrorAction SilentlyContinue)
        if (-not $commands -or $commands.Count -eq 0) {
            continue
        }

        foreach ($command in $commands) {
            $source = [string]$command.Source
            if ($source -match "\\WindowsApps\\(python.exe|python3.exe)$") {
                Write-Log "Ignoring Microsoft Store Python execution alias: $source"
                continue
            }

            $python = $source
            if (-not $python) {
                $python = $candidate
            }

            $versionText = $null
            try {
                $versionText = & $python -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2>$null
            }
            catch {
                Write-Log "Python candidate failed version check: $python"
                continue
            }

            if ($LASTEXITCODE -ne 0 -or -not $versionText) {
                Write-Log "Python candidate did not execute cleanly: $python"
                continue
            }

            try {
                $version = [version]($versionText | Select-Object -First 1)
            }
            catch {
                Write-Log "Python candidate returned an unreadable version: $python"
                continue
            }

            if ($version -ge [version]"3.11") {
                return $python
            }

            Write-Log "Python candidate is older than 3.11: $python ($version)"
        }
    }

    return $null
}

function Test-PythonAvailable {
    return [bool](Get-PythonCommand)
}

function Assert-PythonAvailable {
    if (-not (Test-PythonAvailable)) {
        throw "Python 3.11 or newer is required, and Microsoft Store execution aliases do not count as a working Python install."
    }
}

function Invoke-Step {
    param([string[]]$Command)

    if (-not $Command -or $Command.Count -eq 0) {
        throw "Invoke-Step requires a command array."
    }

    Write-Log ("Running: {0}" -f ($Command -join " "))

    if ($DryRun) {
        Write-Log "DryRun: skipped external command."
        return
    }

    $executable = $Command[0]
    $arguments = @()
    if ($Command.Count -gt 1) {
        $arguments = $Command[1..($Command.Count - 1)]
    }

    & $executable @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
    }
}

function Install-WingetPackage {
    param(
        [string]$PackageId,
        [string]$CommandName,
        [switch]$ForceInstall
    )

    if (-not $ForceInstall -and (Test-CommandAvailable $CommandName)) {
        Write-Log "$CommandName is already available; skipping $PackageId."
        return
    }

    if (-not (Test-CommandAvailable "winget")) {
        Write-State @{
            blocked = $true
            blocked_reason = "winget_missing"
            missing_package = $PackageId
        }
        throw "winget is required to install $PackageId, but winget is not available."
    }

    Write-Log "Running winget install --id $PackageId."
    Invoke-Step @(
        "winget",
        "install",
        "--id",
        $PackageId,
        "--exact",
        "--accept-package-agreements",
        "--accept-source-agreements"
    )
}

function Refresh-PathFromRegistry {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
    Write-Log "Refreshed PATH from registry."
}

function Ensure-Prerequisites {
    Install-WingetPackage -PackageId "Git.Git" -CommandName "git"
    if (-not (Test-PythonAvailable)) {
        Install-WingetPackage -PackageId "Python.Python.3.11" -CommandName "python" -ForceInstall
    }
    Install-WingetPackage -PackageId "OpenJS.NodeJS.LTS" -CommandName "node"
    Refresh-PathFromRegistry
    Assert-PythonAvailable

    if (-not (Test-CommandAvailable "npm")) {
        throw "npm is required after Node.js installation, but npm is not available on PATH."
    }

    if (-not (Test-CommandAvailable "uv")) {
        Invoke-Step @(
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "irm https://astral.sh/uv/install.ps1 | iex"
        )
        Refresh-PathFromRegistry
    }
    else {
        Write-Log "uv is already available."
    }

    Write-State @{ prerequisites_installed = $true }
}

function Ensure-Codex {
    if (-not (Test-CommandAvailable "codex")) {
        Write-Log "Running npm i -g @openai/codex@latest."
        Invoke-Step @("npm", "i", "-g", "@openai/codex@latest")
        Refresh-PathFromRegistry
    }
    else {
        Write-Log "codex is already available."
    }

    if (-not (Test-CommandAvailable "codex")) {
        throw "Codex CLI installation completed, but codex is not available on PATH."
    }

    if (-not (Get-StateValue "codex_login_completed")) {
        Invoke-Step @("codex", "login")
        if (-not $DryRun) {
            Write-State @{ codex_login_completed = $true }
        }
    }
    else {
        Write-Log "Codex login already completed; skipping login."
    }

    Write-State @{ codex_installed = $true }
}

function Ensure-Repo {
    $gitDir = Join-Path $InstallDir ".git"

    if (Test-Path $gitDir) {
        $originUrl = $null
        try {
            $originUrl = (& git -C $InstallDir remote get-url origin 2>$null | Select-Object -First 1)
        }
        catch {
            $originUrl = $null
        }
        if ($originUrl -and $originUrl.Trim() -ne $RepoUrl) {
            throw "Existing checkout origin is '$($originUrl.Trim())', expected '$RepoUrl'. Refusing to switch repositories."
        }
        Invoke-Step @("git", "-C", $InstallDir, "fetch", "origin", $Branch)
        Invoke-Step @("git", "-C", $InstallDir, "checkout", $Branch)
        Invoke-Step @("git", "-C", $InstallDir, "pull", "--ff-only", "origin", $Branch)
    }
    else {
        $parent = Split-Path -Parent $InstallDir
        Write-Log "Creating install parent: $parent"
        if (-not $DryRun) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        Invoke-Step @("git", "clone", "--branch", $Branch, $RepoUrl, $InstallDir)
    }

    Write-State @{ repo_ready = $true }
}

function Invoke-CodexHandoff {
    $orchestrator = Join-Path $InstallDir "project-brain\capabilities\skills\onboard\scripts\windows_one_click.py"
    Assert-PythonAvailable
    $pythonCommand = Get-PythonCommand
    $orchestratorCommand = @($pythonCommand, $orchestrator, "--run", "--repo-root", $InstallDir)
    if ($VaultRepo) {
        $orchestratorCommand += @("--vault-repo", $VaultRepo)
    }
    if ($VaultDir) {
        $orchestratorCommand += @("--vault-dir", $VaultDir)
    }
    if ($InitLocalVault) {
        $orchestratorCommand += "--init-local-vault"
    }
    if ($NoVaultPrompt) {
        $orchestratorCommand += "--no-vault-prompt"
    }

    Write-Log ("Local orchestrator command: {0}" -f ($orchestratorCommand -join " "))

    if ($NoLaunch -or $DryRun) {
        Write-Log "Skipping repo-owned orchestrator because NoLaunch or DryRun is set."
        return $false
    }

    Push-Location $InstallDir
    try {
        Invoke-Step $orchestratorCommand
    }
    finally {
        Pop-Location
    }

    return $true
}

try {
    Write-Log "Starting Augur Windows one-click bootstrap."
    Write-State @{
        install_dir = $InstallDir
        repo_url = $RepoUrl
        branch = $Branch
        vault_repo = $VaultRepo
        vault_dir = $VaultDir
        init_local_vault = [bool]$InitLocalVault
        no_vault_prompt = [bool]$NoVaultPrompt
        dry_run = [bool]$DryRun
        no_launch = [bool]$NoLaunch
        started = $true
    }

    Ensure-Prerequisites
    Ensure-Codex
    Ensure-Repo
    $handoffCompleted = Invoke-CodexHandoff

    if (-not $handoffCompleted) {
        Write-State @{
            completed = $false
            blocked = $false
            handoff_skipped = $true
            completion_reason = "codex_handoff_skipped"
        } -ClearKeys @("error", "blocked_reason", "missing_package")
        Write-Log "Augur Windows one-click bootstrap prepared repo but skipped Codex handoff."
        exit 0
    }

    Write-State @{
        completed = $true
        blocked = $false
        handoff_skipped = $false
        handoff_completed = $true
    } -ClearKeys @("error", "blocked_reason", "missing_package", "completion_reason")
    Write-Log "Augur Windows one-click bootstrap completed."
}
catch {
    Write-State @{
        completed = $false
        blocked = $true
        error = $_.Exception.Message
    }
    Write-Log "Augur Windows one-click bootstrap failed: $($_.Exception.Message)"
    throw
}
