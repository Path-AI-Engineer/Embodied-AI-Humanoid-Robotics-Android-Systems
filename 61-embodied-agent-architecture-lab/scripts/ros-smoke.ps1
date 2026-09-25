param([switch]$SkipBuild, [ValidateRange(1, 12)][int]$Runs = 1)

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
timeout 45s ros2 launch astra_bringup headless.launch.py > /tmp/astra-bringup.log 2>&1 &
launch_pid=$!
sleep 8
ros2 bag record -o /tmp/astra-bag --storage sqlite3 --polling-interval 100 --topics /astra/safety/state /astra/safety/faults /astra/safety/recovery /astra/control/intent /astra/control/authorized_cmd_vel /astra/goals/request /astra/goals/decision /astra/perception/percepts /astra/world/entities /clock > /tmp/astra-bag.log 2>&1 &
bag_pid=$!
sleep 2
python3 /ws/src/embodied_safety/test/ros_gate_probe.py > /tmp/astra-probe.log 2>&1
probe_status=$?
kill -TERM $bag_pid 2>/dev/null || true
wait $bag_pid 2>/dev/null || true
python3 /ws/src/embodied_safety/test/verify_rosbag.py > /tmp/astra-bag-verification.log 2>&1
bag_status=$?
kill $launch_pid 2>/dev/null || true
wait $launch_pid 2>/dev/null || true
cat /tmp/astra-bringup.log
cat /tmp/astra-probe.log
if [ "$probe_status" -ne 0 ]; then exit 19; fi
cat /tmp/astra-bag-verification.log
if [ "$bag_status" -ne 0 ]; then cat /tmp/astra-bag.log; exit 20; fi
if grep -Eq 'symbol lookup error|process has died|\[ERROR\]' /tmp/astra-bringup.log; then exit 14; fi
if ! grep -q 'Entity creation successful' /tmp/astra-bringup.log; then exit 15; fi
if ! grep -q 'Robot initialized' /tmp/astra-bringup.log; then exit 16; fi
if ! grep -q 'Creating GZ->ROS Bridge' /tmp/astra-bringup.log; then exit 17; fi
echo 'Project 61 ROS/Gazebo and motor safety smoke passed.'
'@
    for ($runIndex = 1; $runIndex -le $Runs; $runIndex++) {
        Write-Host "  -> Clean ROS/Gazebo bringup $runIndex/$Runs" -ForegroundColor Cyan
        $output = docker run --rm --memory=4g $image bash -lc $smoke 2>&1
        if ($LASTEXITCODE -ne 0) {
            $output | Out-Host
            throw "ROS/Gazebo smoke failed on run $runIndex with exit code $LASTEXITCODE."
        }
        if ($Runs -eq 1) { $output | Out-Host }
        else {
            $output | Where-Object { $_ -match 'Project 61 ROS/Gazebo and motor safety smoke passed|estop_to_recovery_zero_motion' } | Out-Host
        }
    }
    Write-Host "All $Runs clean ROS/Gazebo bringups passed." -ForegroundColor Green
}
finally { Pop-Location }
