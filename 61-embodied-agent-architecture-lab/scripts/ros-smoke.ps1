param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$image = 'embodied-project61-ros:quality'
Push-Location $root
try {
    if (-not $SkipBuild) {
        Write-Host '  -> Building the pinned Lyrical/Jetty image' -ForegroundColor Cyan
        docker build --quiet -f Dockerfile.ros -t $image .
        if ($LASTEXITCODE -ne 0) { throw 'ROS image build failed.' }
    }

    $smoke = @'
. /opt/ros/lyrical/setup.bash
. /ws/install/setup.bash
export AMENT_PREFIX_PATH=/ws/install:$AMENT_PREFIX_PATH
set -u
ros2 interface show astra_interfaces/msg/Percept >/dev/null || exit 10
ros2 interface show astra_interfaces/action/SkillInvocation >/dev/null || exit 11
xacro /ws/install/share/astra_description/urdf/astra.urdf.xacro >/dev/null || exit 12
gz sdf -k /ws/install/share/astra_simulation/worlds/embodied_lab.sdf >/dev/null || exit 13
timeout 20s ros2 launch astra_bringup headless.launch.py > /tmp/astra-bringup.log 2>&1
status=$?
cat /tmp/astra-bringup.log
if grep -Eq 'symbol lookup error|process has died|\[ERROR\]' /tmp/astra-bringup.log; then exit 14; fi
if ! grep -q 'Entity creation successful' /tmp/astra-bringup.log; then exit 15; fi
if ! grep -q 'Robot initialized' /tmp/astra-bringup.log; then exit 16; fi
if ! grep -q 'Creating GZ->ROS Bridge' /tmp/astra-bringup.log; then exit 17; fi
if [ "$status" -ne 0 ] && [ "$status" -ne 124 ]; then
  echo "launch returned unexpected status $status" >&2
  exit 18
fi
echo 'Project 61 ROS/Gazebo headless smoke passed.'
'@
    Write-Host '  -> ROS interfaces, robot/world syntax, headless spawn' -ForegroundColor Cyan
    docker run --rm --memory=4g $image bash -lc $smoke
    if ($LASTEXITCODE -ne 0) { throw "ROS/Gazebo smoke failed with exit code $LASTEXITCODE." }
}
finally { Pop-Location }
