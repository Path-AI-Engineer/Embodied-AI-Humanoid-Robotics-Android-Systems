param([switch]$SkipBuild, [ValidateRange(1, 12)][int]$Runs = 1, [switch]$CaptureBag, [string]$Image = 'embodied-project61-ros:quality', [string]$ReportPath = '')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$image = $Image
if ($CaptureBag -and $Runs -ne 1) {
    throw '-CaptureBag requires -Runs 1 so the preserved bag has one unambiguous run.'
}
$captureDirectory = $null
$profileHasher = [Security.Cryptography.SHA256]::Create()
try {
    $profileHash = [BitConverter]::ToString($profileHasher.ComputeHash([IO.File]::ReadAllBytes((Join-Path $root 'configs\robotics-profile.lock')))).Replace('-', '').ToLowerInvariant()
}
finally { $profileHasher.Dispose() }
$campaign = [ordered]@{
    schema_version = 'astra.ros-bringup-campaign.v1'
    image = $image
    image_id = ''
    robotics_profile_sha256 = $profileHash
    requested_runs = $Runs
    results = @()
}
function Save-CampaignReport {
    if (-not $ReportPath) { return }
    $resolvedReport = if ([IO.Path]::IsPathRooted($ReportPath)) { $ReportPath } else { Join-Path $root $ReportPath }
    $reportDirectory = Split-Path -Parent $resolvedReport
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    $campaign | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resolvedReport -Encoding utf8
}
if ($CaptureBag) {
    $captureDirectory = Join-Path $root ('reports\local\ros-evidence\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $captureDirectory -Force | Out-Null
}
Push-Location $root
try {
    if (-not $SkipBuild) {
        Write-Host '  -> Building the pinned Lyrical/Jetty image' -ForegroundColor Cyan
        docker build --quiet -f Dockerfile.ros -t $image .
        if ($LASTEXITCODE -ne 0) { throw 'ROS image build failed.' }
    }
    $campaign.image_id = (docker image inspect --format '{{.Id}}' $image).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'ROS image inspect failed.' }

    $smoke = @'
. /opt/ros/lyrical/setup.bash
. /ws/install/setup.bash
export AMENT_PREFIX_PATH=/ws/install:$AMENT_PREFIX_PATH
set -u
ros2 interface show astra_interfaces/msg/Percept >/dev/null || exit 10
ros2 interface show astra_interfaces/action/SkillInvocation >/dev/null || exit 11
xacro /ws/install/share/astra_description/urdf/astra.urdf.xacro >/dev/null || exit 12
gz sdf -k /ws/install/share/astra_simulation/worlds/embodied_lab.sdf >/dev/null || exit 13
timeout 240s ros2 launch astra_bringup headless.launch.py > /tmp/astra-bringup.log 2>&1 &
launch_pid=$!
sleep 8
wait_active() {
  for attempt in $(seq 1 20); do
    if timeout 3s ros2 lifecycle get "$1" 2>/dev/null | grep -Eq '^active \[[0-9]+\]$'; then return 0; fi
    sleep 1
  done
  return 1
}
wait_state() {
  expected="$1"
  for attempt in $(seq 1 10); do
    if timeout 5s ros2 lifecycle get /world_model 2>/dev/null | grep -Eq "^$expected \\[[0-9]+\\]$"; then return 0; fi
    sleep 0.3
  done
  return 1
}
if ! wait_active /lidar_perception; then
  echo 'lidar lifecycle activation timed out' >&2
  timeout 5s ros2 lifecycle get /lidar_perception 2>&1 || true
  grep -E 'lifecycle_bootstrap|lidar_perception' /tmp/astra-bringup.log | tail -n 35 || true
  exit 21
fi
if ! wait_active /camera_perception; then
  echo 'camera lifecycle activation timed out' >&2
  timeout 5s ros2 lifecycle get /camera_perception 2>&1 || true
  grep -E 'lifecycle_bootstrap|camera_perception' /tmp/astra-bringup.log | tail -n 35 || true
  exit 24
fi
if ! wait_active /world_model; then
  echo 'world lifecycle activation timed out' >&2
  timeout 5s ros2 lifecycle get /world_model 2>&1 || true
  grep 'world_lifecycle' /tmp/astra-bringup.log | tail -n 12 || true
  exit 22
fi
controllers_ready=0
for attempt in $(seq 1 30); do
  controller_state=$(timeout 5s ros2 control list_controllers -c /controller_manager 2>/dev/null || true)
  if echo "$controller_state" | grep -q 'joint_state_broadcaster.*active'; then
    if ! echo "$controller_state" | grep -q 'arm_controller.*active'; then sleep 1; continue; fi
    controllers_ready=1
    break
  fi
  sleep 1
done
if [ "$controllers_ready" -ne 1 ]; then
  printf 'arm_controllers_inactive:%s\n' "$controller_state"
  tail -n 40 /tmp/astra-bringup.log
  kill -TERM $launch_pid 2>/dev/null || true
  exit 28
fi
interfaces=''
for attempt in $(seq 1 30); do
  interfaces=$(timeout 5s ros2 control list_hardware_interfaces -c /controller_manager 2>/dev/null || true)
  if echo "$interfaces" | grep -Eq 'arm_joint_6/position[[:space:]]+\[available\][[:space:]]+\[claimed\]'; then break; fi
  sleep 1
done
for joint in $(seq 1 6); do
  if ! echo "$interfaces" | grep -Eq "arm_joint_${joint}/position[[:space:]]+\[available\][[:space:]]+\[claimed\]"; then
    printf 'arm_joint_%s_position_unclaimed\n' "$joint"
    printf 'hardware_interfaces:%s\n' "$interfaces"
    tail -n 50 /tmp/astra-bringup.log
    kill -TERM $launch_pid 2>/dev/null || true
    exit 29
  fi
done
echo 'six_axis_arm_controller: active'
bag_topics='/astra/safety/state /astra/safety/faults /astra/safety/recovery /astra/control/intent /astra/control/authorized_cmd_vel /astra/goals/request /astra/goals/decision /astra/perception/percepts /astra/world/entities /astra/skills/catalog /astra/skills/feedback /astra/skills/spoken_report /astra/evidence/mission_events /joint_states /arm_controller/controller_state /clock'
if [ -n "${ASTRA_EVIDENCE_DIR:-}" ]; then
  bag_topics="$bag_topics /astra/sensors/scan /astra/sensors/rgbd/image /astra/sensors/rgbd/depth_image /astra/sensors/odom /tf /tf_static"
fi
ros2 bag record -o /tmp/astra-bag --storage sqlite3 --polling-interval 100 --topics $bag_topics > /tmp/astra-bag.log 2>&1 &
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
python3 /ws/src/astra_moveit_config/test/planning_probe.py > /tmp/astra-moveit-probe.log 2>&1
moveit_status=$?
if [ "$moveit_status" -ne 0 ]; then
  cat /tmp/astra-moveit-probe.log
  grep -E 'move_group|MoveIt|OMPL|planning' /tmp/astra-bringup.log | tail -n 60 || true
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 31
fi
python3 /ws/src/embodied_safety/test/arm_estop_probe.py > /tmp/astra-arm-stop.log 2>&1
arm_stop_status=$?
if [ "$arm_stop_status" -ne 0 ]; then
  cat /tmp/astra-arm-stop.log
  echo 'camera_lifecycle_after_failure:'
  timeout 5s ros2 lifecycle get /camera_perception 2>&1 || true
  echo 'rgb_publisher_after_failure:'
  timeout 5s ros2 topic info /astra/sensors/rgbd/image -v 2>&1 | head -n 24 || true
  echo 'camera_processing_after_failure:'
  grep -E 'camera_perception|rgbd_pairing|rgbd|depth_image' /tmp/astra-bringup.log | tail -n 30 || true
  echo 'world_intake_after_failure:'
  grep 'world_intake' /tmp/astra-bringup.log | tail -n 15 || true
  echo 'world_lifecycle_after_failure:'
  timeout 5s ros2 lifecycle get /world_model 2>&1 || true
  grep 'world_lifecycle' /tmp/astra-bringup.log | tail -n 12 || true
  echo 'percept_graph_after_failure:'
  timeout 5s ros2 topic info /astra/perception/percepts -v 2>&1 | head -n 80 || true
  echo 'camera_source_graph_after_failure:'
  timeout 5s ros2 topic info /astra/perception/camera -v 2>&1 | head -n 48 || true
  echo 'lidar_source_graph_after_failure:'
  timeout 5s ros2 topic info /astra/perception/lidar -v 2>&1 | head -n 48 || true
  echo 'object_target_graph_after_failure:'
  timeout 5s ros2 topic info /astra/world/object_target -v 2>&1 | head -n 48 || true
  echo 'planner_service_after_failure:'
  timeout 5s ros2 service list 2>/dev/null | grep plan_kinematic_path || true
  grep 'rgbd_pairing' /tmp/astra-bringup.log | tail -n 10 || true
  grep -E 'move_group.*(process has died|\[ERROR\]|shutdown|terminat)' /tmp/astra-bringup.log | tail -n 20 || true
  grep -E 'arm_control_gateway|safety_gateway|move_group|plan_kinematic_path' /tmp/astra-bringup.log | tail -n 30 || true
  tail -n 40 /tmp/astra-bringup.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 30
fi
python3 /ws/src/embodied_skills/test/skill_action_probe.py > /tmp/astra-skill-probe.log 2>&1
skill_status=$?
if [ "$skill_status" -ne 0 ]; then
  cat /tmp/astra-skill-probe.log
  tail -n 30 /tmp/astra-bringup.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 25
fi
python3 /ws/src/embodied_executive/test/executive_probe.py > /tmp/astra-executive-probe.log 2>&1
executive_status=$?
if [ "$executive_status" -ne 0 ]; then
  cat /tmp/astra-executive-probe.log
  grep -E 'arm_control_gateway|mission_executive|safety_gateway.*(STOP|arm|recovery)' /tmp/astra-bringup.log | tail -n 30 || true
  tail -n 30 /tmp/astra-bringup.log
  kill -TERM $bag_pid $launch_pid 2>/dev/null || true
  exit 26
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
grep -E 'Entity creation successful|Robot initialized|Creating GZ->ROS Bridge|rgbd_pairing' /tmp/astra-bringup.log | tail -n 8 || true
cat /tmp/astra-moveit-probe.log
cat /tmp/astra-arm-stop.log
cat /tmp/astra-executive-probe.log
cat /tmp/astra-skill-probe.log
cat /tmp/astra-probe.log
if [ "$skill_status" -ne 0 ]; then exit 25; fi
if [ "$arm_stop_status" -ne 0 ]; then exit 30; fi
if [ "$moveit_status" -ne 0 ]; then exit 31; fi
if [ "$probe_status" -ne 0 ]; then exit 19; fi
if [ "$lifecycle_status" -ne 0 ]; then cat /tmp/astra-lifecycle.log; exit 23; fi
cat /tmp/astra-bag-verification.log
if [ "$bag_status" -ne 0 ]; then cat /tmp/astra-bag.log; exit 20; fi
if [ -n "${ASTRA_EVIDENCE_DIR:-}" ]; then
  cp -a /tmp/astra-bag "$ASTRA_EVIDENCE_DIR/rosbag"
  cp /tmp/astra-bag-verification.log "$ASTRA_EVIDENCE_DIR/verification.json"
  cp /tmp/astra-executive-probe.log "$ASTRA_EVIDENCE_DIR/executive-probe.log"
  cp /tmp/astra-arm-stop.log "$ASTRA_EVIDENCE_DIR/arm-stop-probe.log"
  cp /tmp/astra-moveit-probe.log "$ASTRA_EVIDENCE_DIR/moveit-probe.log"
  cp /tmp/astra-probe.log "$ASTRA_EVIDENCE_DIR/safety-probe.log"
fi
arm_clamps=$(grep -c 'Command of at least one joint is out of limits' /tmp/astra-bringup.log || true)
echo "arm_command_clamps:$arm_clamps"
if [ "$arm_clamps" -gt 25 ]; then
  echo 'arm_controller_saturation_exceeded'
  exit 14
fi
unexpected_errors=$(grep -E 'symbol lookup error|process has died|\[ERROR\]' /tmp/astra-bringup.log | grep -Ev 'Command of at least one joint is out of limits|No 3D sensor plugin\(s\) defined for octomap updates' || true)
if [ -n "$unexpected_errors" ]; then
  echo 'bringup_error_lines:'
  printf '%s\n' "$unexpected_errors"
  exit 14
fi
if ! grep -q 'Entity creation successful' /tmp/astra-bringup.log; then exit 15; fi
if ! grep -q 'Robot initialized' /tmp/astra-bringup.log; then exit 16; fi
if ! grep -q 'Creating GZ->ROS Bridge' /tmp/astra-bringup.log; then exit 17; fi
echo 'Project 61 ROS/Gazebo and motor safety smoke passed.'
'@
    for ($runIndex = 1; $runIndex -le $Runs; $runIndex++) {
        Write-Host "  -> Clean ROS/Gazebo bringup $runIndex/$Runs" -ForegroundColor Cyan
        $runStarted = Get-Date
        $priorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $dockerOptions = @('--rm', '--memory=4g')
            if ($CaptureBag) {
                $dockerOptions += @('--mount', "type=bind,source=$captureDirectory,target=/evidence", '-e', 'ASTRA_EVIDENCE_DIR=/evidence')
            }
            $encodedSmoke = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($smoke))
            $smokeCommand = "echo $encodedSmoke | base64 -d > /tmp/astra-run-smoke.sh && bash /tmp/astra-run-smoke.sh"
            $output = docker run @dockerOptions $image bash -lc $smokeCommand 2>&1
            $runExitCode = $LASTEXITCODE
        }
        finally { $ErrorActionPreference = $priorActionPreference }
        $verification = $output | Where-Object { $_ -match '^\{"arm_samples_within_limits"' } | Select-Object -Last 1
        $campaign.results += [ordered]@{
            run = $runIndex
            exit_code = $runExitCode
            wall_seconds = [math]::Round(((Get-Date) - $runStarted).TotalSeconds, 3)
            rosbag_verification = if ($verification) { $verification | ConvertFrom-Json } else { $null }
            camera_diagnostics = if ($runExitCode -ne 0) { @($output | Where-Object { $_ -match 'rgbd_pairing|camera_perception|/camera|image_raw|depth/image_raw' } | Select-Object -Last 40) } else { @() }
            failure_excerpt = if ($runExitCode -ne 0) { ($output | Select-Object -Last 250) -join "`n" } else { $null }
        }
        Save-CampaignReport
        if ($runExitCode -ne 0) {
            $output | Out-Host
            throw "ROS/Gazebo smoke failed on run $runIndex with exit code $runExitCode."
        }
        if ($Runs -eq 1) { $output | Out-Host }
        else {
            $output | Where-Object { $_ -match 'Project 61 ROS/Gazebo and motor safety smoke passed|estop_to_recovery_zero_motion' } | Out-Host
        }
    }
    Write-Host "All $Runs clean ROS/Gazebo bringups passed." -ForegroundColor Green
    if ($CaptureBag) { Write-Host "Preserved ROS evidence: $captureDirectory" -ForegroundColor Green }
}
finally { Pop-Location }
