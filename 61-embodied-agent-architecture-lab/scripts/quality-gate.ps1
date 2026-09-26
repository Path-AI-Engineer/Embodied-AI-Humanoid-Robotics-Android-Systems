param([string]$Python = '', [switch]$SkipWeb, [switch]$RequireRos)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Project Python is missing. Run .\scripts\setup.ps1 first or pass -Python <absolute path>.'
}
function Assert-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE." }
}
$oldPath = $env:PYTHONPATH
$oldPython = $env:EMBODIED_PYTHON
$oldRoot = $env:EMBODIED_PROJECT_ROOT
$env:PYTHONPATH = Join-Path $projectRoot 'src'
$env:EMBODIED_PYTHON = $Python
$env:EMBODIED_PROJECT_ROOT = $projectRoot
Push-Location $projectRoot
try {
    Write-Host '  -> Ruff lint and format' -ForegroundColor Cyan
    & $Python -m ruff check src tests scripts embodied_observation embodied_goals embodied_safety embodied_skills embodied_executive
    Assert-Exit 'Ruff lint'
    & $Python -m ruff format --check src tests scripts embodied_observation embodied_goals embodied_safety embodied_skills embodied_executive
    Assert-Exit 'Ruff format'
    Write-Host '  -> Development scenario evaluation' -ForegroundColor Cyan
    & $Python -m embodied.cli evaluate --split development --out reports/local
    Assert-Exit 'Development evaluation'
    Write-Host '  -> Unit and API tests' -ForegroundColor Cyan
    & $Python -m unittest discover -s tests -v
    Assert-Exit 'Unit and API tests'
    Write-Host '  -> Data-only handoff candidate checksums' -ForegroundColor Cyan
    & $Python scripts/verify_contract_handoff.py
    Assert-Exit 'Contract handoff candidate'
    if (-not $SkipWeb) {
        Push-Location (Join-Path $projectRoot 'apps\workbench')
        try {
            Write-Host '  -> Web TypeScript, lint, build, Playwright' -ForegroundColor Cyan
            npm run typecheck
            Assert-Exit 'Web TypeScript'
            npm run lint
            Assert-Exit 'Web lint'
            npm run build
            Assert-Exit 'Web build'
            npm run test:e2e
            Assert-Exit 'Web Playwright'
        }
        finally { Pop-Location }
    }
    if ($RequireRos) {
        & (Join-Path $PSScriptRoot 'ros-smoke.ps1')
        Assert-Exit 'ROS/Gazebo smoke'
        & (Join-Path $PSScriptRoot 'security-smoke.ps1')
        Assert-Exit 'SROS2 allow/deny fixture'
    }
    git -c "safe.directory=$(Split-Path -Parent $projectRoot)" diff --check
    Assert-Exit 'git diff --check'
    Write-Host 'Project 61 selected local gates passed. Full project closure requires the frozen test and handoff gates.' -ForegroundColor Green
}
finally {
    Pop-Location
    $env:PYTHONPATH = $oldPath
    $env:EMBODIED_PYTHON = $oldPython
    $env:EMBODIED_PROJECT_ROOT = $oldRoot
}
