# Test Suite for SSL Configuration Logic
# Run with: pwsh tests/test_ssl_logic.ps1

$ScriptPath = Join-Path $PSScriptRoot "../../install.ps1"
$TestTempDir = Join-Path $PSScriptRoot "temp_test_data"

Write-Host "Loading install.ps1 logic..." -ForegroundColor Cyan
. $ScriptPath

# -----------------------------------------------------------------------------
# Mocks & Helpers
# -----------------------------------------------------------------------------
function Assert-Equal {
    param($Actual, $Expected, $Message)
    if ($Actual -eq $Expected) {
        Write-Host "[PASS] $Message" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Message. Expected '$Expected', got '$Actual'" -ForegroundColor Red
    }
}

function Setup-TestDir {
    if (Test-Path $TestTempDir) { Remove-Item -Recurse -Force $TestTempDir }
    New-Item -ItemType Directory -Path $TestTempDir | Out-Null
    return $TestTempDir
}

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

# TEST 1: Config Persistence
Write-Host "`nTest 1: Config Persistence (Get/Set-ExoConfig)" -ForegroundColor Yellow
$dir = Setup-TestDir
$testConfig = @{ trust_system_certs = $true; other_setting = "foo" }

Set-ExoConfig -DataDir $dir -Config $testConfig
$loaded = Get-ExoConfig -DataDir $dir

Assert-Equal $loaded.trust_system_certs $true "Config saved and loaded boolean correctly"
Assert-Equal $loaded.other_setting "foo" "Config saved and loaded string correctly"
Assert-Equal (Test-Path "$dir\.agent\config.json") $true "Config file created"

# TEST 2: Configure-SSL - Priority Logic
Write-Host "`nTest 2: Configure-SSL Logic" -ForegroundColor Yellow

# Mock dependencies to avoid actual system changes
function Write-Info($m) { Write-Host "  [INFO] $m" -ForegroundColor Gray }
function Write-Success($m) { Write-Host "  [OK] $m" -ForegroundColor Gray }
function Write-Warning($m) { Write-Host "  [WARN] $m" -ForegroundColor Gray }
function Write-Step($m) {}
function Test-Command($c) { return $true }
function git { } # Mock git
function npm { } # Mock npm

# Scenario A: Flag Explicitly True -> Should Enable & Save
$dir = Setup-TestDir
$flag = $true
# We redefined Set-ExoConfig via dot-source, but let's use the real one since we set up the dir
# But wait, Configure-SSL calls Set-ExoConfig internally.

Write-Host "- Scenario A: Explicit Flag"
Configure-SSL -TrustSystemCertsRef ([ref]$flag)
$saved = Get-ExoConfig -DataDir $DATA_DIR # Wait, Configure-SSL uses Global $DATA_DIR
# We need to mock $DATA_DIR
$DATA_DIR = $dir
Configure-SSL -TrustSystemCertsRef ([ref]$flag)
$saved = Get-ExoConfig -DataDir $dir
Assert-Equal $flag $true "Flag remains true"
Assert-Equal $saved.trust_system_certs $true "Preference saved to disk"

# Scenario B: Flag False, Config True -> Should Enable
$dir = Setup-TestDir
$DATA_DIR = $dir
Set-ExoConfig -DataDir $dir -Config @{ trust_system_certs = $true }
$flag = $false

Write-Host "- Scenario B: Config True, Flag False"
Configure-SSL -TrustSystemCertsRef ([ref]$flag)
Assert-Equal $flag $true "Flag flipped to true based on config"

# Scenario C: Flag False, Config Empty, Network Fail -> Should Enable & Save
$dir = Setup-TestDir
$DATA_DIR = $dir
$flag = $false

# Mock Network Test Failure
function Test-NetworkConnectivity { return $false }

Write-Host "- Scenario C: Network Failure (Auto-Detect)"
Configure-SSL -TrustSystemCertsRef ([ref]$flag)
Assert-Equal $flag $true "Flag flipped to true based on network check"
$saved = Get-ExoConfig -DataDir $dir
Assert-Equal $saved.trust_system_certs $true "Preference saved to disk after auto-detect"

# Scenario D: Flag False, Config Empty, Network OK -> Should Stay False
$dir = Setup-TestDir
$DATA_DIR = $dir
$flag = $false

# Mock Network Test Success
function Test-NetworkConnectivity { return $true }

Write-Host "- Scenario D: Network OK (No Action)"
Configure-SSL -TrustSystemCertsRef ([ref]$flag)
Assert-Equal $flag $false "Flag remains false"
$saved = Get-ExoConfig -DataDir $dir
Assert-Equal $saved.trust_system_certs $null "No preference saved"

# Cleanup
if (Test-Path $TestTempDir) { Remove-Item -Recurse -Force $TestTempDir }
Write-Host "`nDone."
