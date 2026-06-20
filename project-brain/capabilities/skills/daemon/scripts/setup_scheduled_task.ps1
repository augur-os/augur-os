#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet("install", "uninstall", "status", "heal")]
    [string]$Action = "install",
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

function Test-AugurProjectRoot {
    param([string]$Path)

    if (-not $Path) {
        return $false
    }

    $Pyproject = Join-Path $Path "pyproject.toml"
    $PathsPy = Join-Path $Path "src\config\paths.py"
    $SystemConfig = Join-Path $Path "config\system"
    return (Test-Path $Pyproject) -and ((Test-Path $PathsPy) -or (Test-Path $SystemConfig))
}

function Find-AugurProjectRoot {
    param([string]$StartDir)

    $Current = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($StartDir))
    while ($Current) {
        if (Test-AugurProjectRoot $Current.FullName) {
            return $Current.FullName
        }
        $Current = $Current.Parent
    }

    # Transitional fallback for the pre-Task6 repo-root skill layout.
    return [System.IO.Path]::GetFullPath((Join-Path $StartDir "..\..\.."))
}

if (-not $InstallDir) {
    $InstallDir = Find-AugurProjectRoot $PSScriptRoot
}
else {
    $InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
}

$PythonPath = Join-Path $InstallDir ".venv\Scripts\python.exe"
$SharedServiceHealer = Join-Path $InstallDir "project-brain\capabilities\skills\daemon\scripts\service_healer.py"
$LegacyServiceHealer = Join-Path $InstallDir "skills\daemon\scripts\service_healer.py"
$ServiceHealer = if (Test-Path $SharedServiceHealer) { $SharedServiceHealer } else { $LegacyServiceHealer }

if (-not (Test-Path $PythonPath)) {
    throw "Python not found at $PythonPath"
}

if (-not (Test-Path $ServiceHealer)) {
    throw "service_healer.py not found at $ServiceHealer"
}

Push-Location $InstallDir
try {
    & $PythonPath $ServiceHealer $Action
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
