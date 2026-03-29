[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $PSScriptRoot "build_rules.ps1"
$reportPath = Join-Path $repoRoot "dist\build-report.json"
$knownLocalPythonHint = "%LocalAppData%\Programs\Python\Python314\python.exe"
$knownLocalPython = $null
if ($env:LOCALAPPDATA) {
    $knownLocalPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
}

function Resolve-PythonCommand {
    $candidates = @()

    if ($env:RULEMESH_PYTHON) {
        $candidates += [pscustomobject]@{
            Kind = "Path"
            Value = $env:RULEMESH_PYTHON
            Label = "RULEMESH_PYTHON"
        }
    }

    if ($env:SURGE_CONFIG_PYTHON) {
        $candidates += [pscustomobject]@{
            Kind = "Path"
            Value = $env:SURGE_CONFIG_PYTHON
            Label = "SURGE_CONFIG_PYTHON (legacy)"
        }
    }

    $candidates += [pscustomobject]@{
        Kind = "Path"
        Value = (Join-Path $repoRoot ".venv\Scripts\python.exe")
        Label = ".venv"
    }

    if ($knownLocalPython) {
        $candidates += [pscustomobject]@{
            Kind = "Path"
            Value = $knownLocalPython
            Label = "Python314"
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += [pscustomobject]@{
            Kind = "Command"
            Value = $pythonCommand.Source
            Label = "python"
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate.Kind -eq "Path" -and -not (Test-Path $candidate.Value)) {
            continue
        }

        return $candidate
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return [pscustomobject]@{
            Kind = "Launcher"
            Value = $pyLauncher.Source
            Label = "py -3"
        }
    }

throw @"
No usable Python interpreter was found.
You can fix this by:
1. Setting RULEMESH_PYTHON (or the legacy SURGE_CONFIG_PYTHON) to a valid python.exe path
2. Installing Python and making sure python or py -3 is available
3. Using the known local path: $knownLocalPythonHint
"@
}

function Invoke-UnitTests {
    $python = Resolve-PythonCommand
    $env:PYTHONUTF8 = "1"
    $env:PYTHONDONTWRITEBYTECODE = "1"

    Write-Host ("[check] run unit tests with {0}: {1}" -f $python.Label, $python.Value)

    if ($python.Kind -eq "Launcher") {
        & $python.Value -3 -m unittest discover -s tests -p "test_*.py"
    }
    else {
        & $python.Value -m unittest discover -s tests -p "test_*.py"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Unit tests failed."
    }
}

function Invoke-SurgeTestUrlValidation {
    $python = Resolve-PythonCommand
    $validatorScript = Join-Path $PSScriptRoot "validate_surge_test_urls.py"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONDONTWRITEBYTECODE = "1"

    Write-Host ("[check] validate Surge test URLs with {0}: {1}" -f $python.Label, $python.Value)

    if ($python.Kind -eq "Launcher") {
        & $python.Value -3 -B -X utf8 $validatorScript
    }
    else {
        & $python.Value -B -X utf8 $validatorScript
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Surge test URL validation failed."
    }
}

function Assert-OnlyExpectedDirectories {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedNames
    )

    $actual = @(
        Get-ChildItem $RootPath -Directory -ErrorAction Stop |
            Select-Object -ExpandProperty Name |
            Sort-Object
    )
    $expected = @($ExpectedNames | Sort-Object)
    $diff = Compare-Object -ReferenceObject $expected -DifferenceObject $actual
    if ($diff) {
        throw ("Unexpected directories under {0}. Expected: {1}. Actual: {2}" -f $RootPath, ($expected -join ", "), ($actual -join ", "))
    }
}

function Assert-DistTree {
    $requiredDirs = @(
        (Join-Path $repoRoot "dist\surge\rules"),
        (Join-Path $repoRoot "dist\mihomo\classical")
    )
    foreach ($path in $requiredDirs) {
        if (-not (Test-Path $path -PathType Container)) {
            throw "Missing expected output directory: $path"
        }
    }

    $deprecatedDirs = @(
        (Join-Path $repoRoot "dist\surge\domainset"),
        (Join-Path $repoRoot "dist\mihomo\domain"),
        (Join-Path $repoRoot "dist\mihomo\ipcidr")
    )
    foreach ($path in $deprecatedDirs) {
        if (Test-Path $path) {
            throw "Deprecated output directory detected: $path"
        }
    }

    Assert-OnlyExpectedDirectories -RootPath (Join-Path $repoRoot "dist\surge") -ExpectedNames @("rules")
    Assert-OnlyExpectedDirectories -RootPath (Join-Path $repoRoot "dist\mihomo") -ExpectedNames @("classical")
}

function Assert-BuildReport {
    if (-not (Test-Path $reportPath -PathType Leaf)) {
        throw "Missing build report: $reportPath"
    }

    $report = Get-Content $reportPath -Raw -Encoding utf8 | ConvertFrom-Json
    $warningCount = [int]$report.summary.total_warnings
    if ($warningCount -ne 0) {
        throw ("Build warnings must stay at 0, got: {0}" -f $warningCount)
    }
}

Write-Host "[check] run build"
& $buildScript
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Invoke-UnitTests

Write-Host "[check] validate Surge test URLs"
Invoke-SurgeTestUrlValidation

Write-Host "[check] verify dist layout"
Assert-DistTree

Write-Host "[check] verify build warnings"
Assert-BuildReport

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($gitCommand) {
    Write-Host "[check] git status --short"
    & $gitCommand.Source status --short
}
else {
    Write-Host "[check] git not found, skip status output"
}

Write-Host "[check] all checks passed"
