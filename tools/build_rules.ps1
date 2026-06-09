[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $PSScriptRoot "build_rules.py"
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

$python = Resolve-PythonCommand
$env:PYTHONUTF8 = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

Write-Host ("[build_rules.ps1] run with {0}: {1}" -f $python.Label, $python.Value)

if ($python.Kind -eq "Launcher") {
    & $python.Value -3 -B -X utf8 $pythonScript @ScriptArgs
}
else {
    & $python.Value -B -X utf8 $pythonScript @ScriptArgs
}

exit $LASTEXITCODE
