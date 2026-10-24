# Minimal checks for the Python server and AlphaMiniApp. No installs or Android builds.
[CmdletBinding()]
param([string]$Python = "")

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$app = Join-Path $root "AlphaMiniApp"
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-Check {
    param(
        [string]$Name,
        [string]$Directory,
        [string]$Command,
        [string[]]$CommandArgs,
        [string]$RequiredFile = ""
    )

    Write-Host "`n=== $Name ==="
    $code = 1
    Push-Location -LiteralPath $Directory
    try {
        if ($RequiredFile -and -not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
            throw "Missing installed dependency: $RequiredFile. Run npm ci separately."
        }
        $executable = (Get-Command $Command -ErrorAction Stop).Source
        $previousPreference = $ErrorActionPreference
        try {
            # Native tools such as Jest write successful output to stderr too.
            $ErrorActionPreference = "Continue"
            & $executable @CommandArgs
            $code = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousPreference
        }
    }
    catch {
        Write-Host $_.Exception.Message
        $code = 1
    }
    finally {
        Pop-Location
    }
    $results.Add([pscustomobject]@{ Check = $Name; ExitCode = $code })
    Write-Host "CHECK_RESULT: $Name exit=$code"
}

if (-not $Python) {
    $Python = "python"
    foreach ($candidate in @(".venv/Scripts/python.exe", "venv/Scripts/python.exe")) {
        $candidatePath = Join-Path $root $candidate
        if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
            $Python = $candidatePath
            break
        }
    }
}
Write-Host "Python: $Python"
Invoke-Check -Name "Server import" -Directory $root -Command $Python -CommandArgs @("-B", "-c", "import server")

# Smoke tests are mandatory. Missing pytest is a failed check, never a skip.
$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & $Python -B -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)"
    $pytestAvailable = ($LASTEXITCODE -eq 0)
}
finally { $ErrorActionPreference = $previousPreference }
if (-not $pytestAvailable) {
    Write-Host "Missing pytest. Install with: $Python -m pip install -r requirements-dev.txt"
    $results.Add([pscustomobject]@{ Check = "Server pytest"; ExitCode = 1 })
    Write-Host "CHECK_RESULT: Server pytest exit=1"
}
else {
    Invoke-Check -Name "Server pytest" -Directory $root -Command $Python -CommandArgs @("-B", "-m", "pytest", "-q", "tests")
}

$npx = if (Get-Command npx.cmd -ErrorAction SilentlyContinue) { "npx.cmd" } else { "npx" }
Invoke-Check -Name "App TypeScript" -Directory $app -Command $npx -CommandArgs @("--no-install", "tsc", "--noEmit") -RequiredFile (Join-Path $app "node_modules/typescript/bin/tsc")

$appTests = @(Get-ChildItem -LiteralPath $app -File | Where-Object { $_.Name -match '\.(test|spec)\.[jt]sx?$' })
foreach ($name in @("__tests__", "src", "tests", "test")) {
    $directory = Join-Path $app $name
    if (Test-Path -LiteralPath $directory -PathType Container) {
        $appTests += @(Get-ChildItem -LiteralPath $directory -Recurse -File | Where-Object {
            $_.Name -match '\.(test|spec)\.[jt]sx?$' -or ($name -eq "__tests__" -and $_.Extension -match '^\.[jt]sx?$')
        })
    }
}
if ($appTests.Count -gt 0) {
    Invoke-Check -Name "App Jest" -Directory $app -Command $npx -CommandArgs @("--no-install", "jest", "--runInBand") -RequiredFile (Join-Path $app "node_modules/jest/bin/jest.js")
}
else {
    Write-Host "SKIP: App Jest (no existing Jest tests)."
}

Write-Host "`n=== Verify summary ==="
foreach ($result in $results) {
    Write-Host ("{0}: exit {1}" -f $result.Check, $result.ExitCode)
}
if (@($results | Where-Object { $_.ExitCode -ne 0 }).Count -gt 0) { exit 1 }
exit 0
