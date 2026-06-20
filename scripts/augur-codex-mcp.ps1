param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

# Worktree-aware Augur MCP launcher for Codex on Windows.

$ErrorActionPreference = "Stop"

function Resolve-AugurRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $configuredRoot = Resolve-Path -LiteralPath (Join-Path $scriptDir "..") | Select-Object -ExpandProperty Path
    $cwdRoot = (Get-Location).ProviderPath

    $candidates = @(
        $env:AUGUR_PROJECT_ROOT,
        $env:AUGUR_ROOT,
        $env:AUGUR_REPO,
        $configuredRoot,
        $cwdRoot
    )

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $projectFile = Join-Path $candidate "project.yaml"
        if (Test-Path -LiteralPath $projectFile -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate | Select-Object -ExpandProperty Path)
        }
    }

    Write-Error "[augur] Codex MCP could not locate an Augur checkout. checked AUGUR_PROJECT_ROOT=$env:AUGUR_PROJECT_ROOT AUGUR_ROOT=$env:AUGUR_ROOT AUGUR_REPO=$env:AUGUR_REPO configured=$configuredRoot cwd=$cwdRoot"
    exit 1
}

$root = Resolve-AugurRoot

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $python = $venvPython
} else {
    $python = "python"
}

$env:AUGUR_ROOT = $root
$env:PYTHONUNBUFFERED = "1"
$projectCapabilities = Join-Path (Join-Path $root "project-brain") "capabilities"
$mcpPath = Join-Path $root "src\mcp"
$canonicalPythonPath = "$projectCapabilities;$root;$mcpPath"
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $canonicalPythonPath
} else {
    $filteredPath = @()
    foreach ($entry in ($env:PYTHONPATH -split ";")) {
        if ([string]::IsNullOrWhiteSpace($entry)) {
            continue
        }
        $normalized = $entry.TrimEnd("\", "/")
        if (
            $normalized -eq $root.TrimEnd("\", "/") -or
            $normalized -eq $projectCapabilities.TrimEnd("\", "/") -or
            $normalized -eq $mcpPath.TrimEnd("\", "/") -or
            $normalized -like "*\src\mcp" -or
            $normalized -like "*/src/mcp" -or
            $normalized -like "*\project-brain\capabilities" -or
            $normalized -like "*/project-brain/capabilities" -or
            $normalized -like "*\shared-vault" -or
            $normalized -like "*/shared-vault" -or
            (Split-Path -Leaf $normalized) -eq "Augur"
        ) {
            continue
        }
        $filteredPath += $entry
    }
    if ($filteredPath.Count -gt 0) {
        $env:PYTHONPATH = "$canonicalPythonPath;$($filteredPath -join ';')"
    } else {
        $env:PYTHONPATH = $canonicalPythonPath
    }
}

& $python @RemainingArgs
exit $LASTEXITCODE
