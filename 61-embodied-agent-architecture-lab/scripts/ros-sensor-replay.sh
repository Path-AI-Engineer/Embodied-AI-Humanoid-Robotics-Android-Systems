#!/usr/bin/env bash
. /opt/ros/lyrical/setup.bash
. /ws/install/setup.bash
export AMENT_PREFIX_PATH=/ws/install:$AMENT_PREFIX_PATH
set -euo pipefail

if [ ! -f /evidence/rosbag/metadata.yaml ]; then
  echo 'A retained rosbag2 metadata.yaml is required.' >&2
  exit 10
fi

lidar_pid=''
camera_pid=''
world_pid=''
record_pid=''
cleanup() {
  for pid in "$record_pid" "$world_pid" "$camera_pid" "$lidar_pid"; do
    if [ -n "$pid" ]; then kill -TERM "$pid" 2>/dev/null || true; fi
  done
  for pid in "$record_pid" "$world_pid" "$camera_pid" "$lidar_pid"; do
    if [ -n "$pid" ]; then wait "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT

ros2 run embodied_observation lidar_perception --ros-args -p use_sim_time:=true >/tmp/replay-lidar.log 2>&1 &
lidar_pid=$!
ros2 run embodied_observation camera_perception --ros-args -p use_sim_time:=true >/tmp/replay-camera.log 2>&1 &
camera_pid=$!
ros2 run embodied_observation world_model --ros-args -p use_sim_time:=true >/tmp/replay-world.log 2>&1 &
world_pid=$!

for node in /lidar_perception /camera_perception /world_model; do
  ready=0
  for attempt in $(seq 1 30); do
    if timeout 5s ros2 lifecycle set "$node" configure >/dev/null 2>&1; then
      if timeout 5s ros2 lifecycle set "$node" activate >/dev/null 2>&1; then
        ready=1
        break
      fi
    fi
    sleep 0.5
  done
  if [ "$ready" -ne 1 ]; then
    cat /tmp/replay-lidar.log /tmp/replay-camera.log /tmp/replay-world.log
    echo "Lifecycle activation failed: $node" >&2
    exit 11
  fi
done

ros2 bag record -o /tmp/replay-output --storage sqlite3 --topics /astra/perception/percepts /astra/world/entities >/tmp/replay-record.log 2>&1 &
record_pid=$!
sleep 3
if ! kill -0 "$record_pid" 2>/dev/null; then
  cat /tmp/replay-record.log
  exit 12
fi

timeout 180s ros2 bag play /evidence/rosbag --topics /clock /astra/sensors/scan /astra/sensors/rgbd/image /astra/sensors/rgbd/depth_image --rate 1.0 >/tmp/replay-play.log 2>&1 || {
  cat /tmp/replay-play.log
  exit 13
}
sleep 2
kill -TERM "$record_pid" 2>/dev/null || true
wait "$record_pid" 2>/dev/null || true
record_pid=''
if ! python3 /task/scripts/verify_sensor_replay.py /evidence/rosbag /tmp/replay-output >/tmp/replay-verification.log 2>&1; then
  cat /tmp/replay-verification.log
  exit 14
fi
cat /tmp/replay-verification.log
cp -a /tmp/replay-output /output/rosbag
cp /tmp/replay-verification.log /output/verification.log
cp /tmp/replay-play.log /output/player.log
