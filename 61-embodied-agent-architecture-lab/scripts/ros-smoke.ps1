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
timeout 180s ros2 launch astra_bringup headless.launch.py > /tmp/astra-bringup.log 2>&1 &
launch_pid=$!
sleep 8
wait_active() {
  for attempt in $(seq 1 20); do
    if timeout 3s ros2 lifecycle get "$1" 2>/dev/null | grep -q 'active'; then return 0; fi
    sleep 1
  done
  return 1
}
wait_state() {
  expected="$1"
  for attempt in $(seq 1 10); do
    if timeout 5s ros2 lifecycle get /world_model 2>/dev/null | grep -q "$expected"; then return 0; fi
    sleep 0.3
  done
  return 1
}
if ! wait_active /lidar_perception; then echo 'lidar lifecycle activation timed out' >&2; exit 21; fi
if ! wait_active /camera_perception; then echo 'camera lifecycle activation timed out' >&2; exit 24; fi
if ! wait_active /world_model; then echo 'world lifecycle activation timed out' >&2; exit 22; fi
ros2 bag record -o /tmp/astra-bag --storage sqlite3 --polling-interval 100 --topics /astra/safety/state /astra/safety/faults /astra/safety/recovery /astra/control/intent /astra/control/authorized_cmd_vel /astra/goals/request /astra/goals/decision /astra/perception/percepts /astra/world/entities /astra/skills/catalog /astra/skills/feedback /astra/skills/spoken_report /astra/evidence/mission_events /clock > /tmp/astra-bag.log 2>&1 &
bag_pid=$!
bag_ready=0
for attempt in $(seq 1 20); do
  if timeout 5s ros2 topic info /astra/evidence/mission_events 2>/dev/null | grep -Eq 'Subscription count: [1-9]'; then bag_ready=1; break; fi
  sleep 0.3
done
if [ "$bag_ready" -ne 1 ]; then
  cat /tmp/astra-bag.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 27
fi
python3 /ws/src/embodied_executive/test/executive_probe.py > /tmp/astra-executive-probe.log 2>&1
executive_status=$?
if [ "$executive_status" -ne 0 ]; then
  cat /tmp/astra-executive-probe.log
  tail -n 30 /tmp/astra-bringup.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 26
fi
python3 /ws/src/embodied_skills/test/skill_action_probe.py > /tmp/astra-skill-probe.log 2>&1
skill_status=$?
if [ "$skill_status" -ne 0 ]; then
  cat /tmp/astra-skill-probe.log
  tail -n 30 /tmp/astra-bringup.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 25
fi
python3 /ws/src/embodied_safety/test/ros_gate_probe.py > /tmp/astra-probe.log 2>&1
probe_status=$?
timeout 15s ros2 lifecycle set /world_model deactivate > /tmp/astra-lifecycle.log 2>&1
lifecycle_status=$?
if [ "$lifecycle_status" -eq 0 ]; then wait_state inactive || lifecycle_status=1; fi
if [ "$lifecycle_status" -eq 0 ]; then timeout 15s ros2 lifecycle set /world_model activate >> /tmp/astra-lifecycle.log 2>&1 || lifecycle_status=1; fi
if [ "$lifecycle_status" -eq 0 ]; then wait_state active || lifecycle_status=1; fi
kill -TERM $bag_pid 2>/dev/null || true
wait $bag_pid 2>/dev/null || true
python3 /ws/src/embodied_safety/test/verify_rosbag.py > /tmp/astra-bag-verification.log 2>&1
bag_status=$?
kill $launch_pid 2>/dev/null || true
wait $launch_pid 2>/dev/null || true
cat /tmp/astra-bringup.log
cat /tmp/astra-executive-probe.log
cat /tmp/astra-skill-probe.log
cat /tmp/astra-probe.log
if [ "$skill_status" -ne 0 ]; then exit 25; fi
if [ "$probe_status" -ne 0 ]; then exit 19; fi
if [ "$lifecycle_status" -ne 0 ]; then cat /tmp/astra-lifecycle.log; exit 23; fi
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
