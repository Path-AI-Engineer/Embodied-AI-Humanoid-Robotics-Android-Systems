$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$policy = Join-Path $root 'configs\security'
$image = 'embodied-project61-ros:quality'
$smoke = @'
. /opt/ros/lyrical/setup.bash
. /ws/install/setup.bash
export AMENT_PREFIX_PATH=/ws/install:$AMENT_PREFIX_PATH
ros2 security generate_artifacts -k /tmp/astra-keystore -p /policy/sros2-policy.v1.xml || exit 10
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_KEYSTORE=/tmp/astra-keystore
export ROS_SECURITY_STRATEGY=Enforce
python3 /ws/src/embodied_safety/test/sros2_probe.py listener --ros-args --enclave /astra/safety > /tmp/security-listener.log 2>&1 &
listener_pid=$!
sleep 2
python3 /ws/src/embodied_safety/test/sros2_probe.py authorized --ros-args --enclave /astra/safety > /tmp/security-authorized.log 2>&1 &
authorized_pid=$!
python3 /ws/src/embodied_safety/test/sros2_probe.py unauthorized --ros-args --enclave /astra/unauthorized > /tmp/security-unauthorized.log 2>&1 &
unauthorized_pid=$!
wait $authorized_pid
authorized_status=$?
wait $unauthorized_pid || true
wait $listener_pid
listener_status=$?
cat /tmp/security-listener.log
if [ "$authorized_status" -ne 0 ] || [ "$listener_status" -ne 0 ]; then
  cat /tmp/security-authorized.log
  cat /tmp/security-unauthorized.log
  exit 11
fi
echo 'SROS2 publisher allow/deny fixture passed.'
'@
docker run --rm --memory=2g -v "${policy}:/policy:ro" $image bash -lc $smoke
if ($LASTEXITCODE -ne 0) { throw "SROS2 security smoke failed with exit code $LASTEXITCODE." }
