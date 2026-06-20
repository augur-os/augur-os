#Requires -Version 5.1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$attemptedRuntimes = @(".venv\Scripts\python.exe", "uv run python", "py -3", "python")
$RemainingArgs = @($args)

function Get-AugurPython {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @($venvPython)
    }

    $uv = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($uv) {
        return @($uv.Source, "run", "python")
    }

    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, "-3")
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    throw "Could not find a Python runtime for Augur launchers from repo root: $RepoRoot. Attempted: $($attemptedRuntimes -join ', ')"
}

$pythonCommand = @(Get-AugurPython)
$exe = $pythonCommand[0]
$prefixArgs = @()
if ($pythonCommand.Count -gt 1) {
    $prefixArgs = $pythonCommand[1..($pythonCommand.Count - 1)]
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RepoRoot;$($env:PYTHONPATH)"
} else {
    $env:PYTHONPATH = $RepoRoot
}

$exitCode = 0
$TempFile = [System.IO.Path]::GetTempFileName()
$env:AUGUR_LAST_WORKTREE_FILE = $TempFile

Push-Location $RepoRoot
try {
    & $exe @prefixArgs -m src.scripts.agent_launch --client claude @RemainingArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
    $newWorktree = $null
    if (Test-Path $TempFile) {
        $content = Get-Content $TempFile -Raw
        if ($content) {
            $newWorktree = $content.Trim()
        }
        Remove-Item $TempFile -ErrorAction SilentlyContinue
    }
    $env:AUGUR_LAST_WORKTREE_FILE = $null
    if ($newWorktree -and (Test-Path $newWorktree)) {
        Set-Location $newWorktree
    }
}
exit $exitCode
