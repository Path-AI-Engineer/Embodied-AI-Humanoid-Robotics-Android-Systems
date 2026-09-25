param([string]$BasePython = '')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $BasePython) {
    $candidate = Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $candidate) { throw 'Python >=3.11 is required. Pass -BasePython <absolute path>.' }
    $BasePython = $candidate.Source
}
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $BasePython -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}
& $venvPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
& $venvPython -m pip install -e "${root}[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Python dependency install failed.' }
Push-Location (Join-Path $root 'apps\workbench')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Workbench dependency install failed.' }
}
finally { Pop-Location }
Write-Host 'Project 61 portable dependencies are ready.' -ForegroundColor Green
