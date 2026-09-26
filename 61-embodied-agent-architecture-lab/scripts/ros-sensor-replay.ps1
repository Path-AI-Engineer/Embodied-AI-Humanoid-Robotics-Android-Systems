param([Parameter(Mandatory = $true)][string]$EvidenceDirectory)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$evidence = (Resolve-Path -LiteralPath $EvidenceDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $evidence 'rosbag\metadata.yaml'))) {
    throw 'The evidence directory must contain rosbag\metadata.yaml.'
}
$replayEvidence = Join-Path $root ('reports\local\sensor-replay\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $replayEvidence -Force | Out-Null

docker run --rm --memory=4g `
    --mount "type=bind,source=$evidence,target=/evidence,readonly" `
    --mount "type=bind,source=$replayEvidence,target=/output" `
    --mount "type=bind,source=$root,target=/task,readonly" `
    embodied-project61-ros:quality bash /task/scripts/ros-sensor-replay.sh
if ($LASTEXITCODE -ne 0) { throw "ROS sensor replay failed with exit code $LASTEXITCODE." }
Write-Host "Preserved sensor replay evidence: $replayEvidence" -ForegroundColor Green
