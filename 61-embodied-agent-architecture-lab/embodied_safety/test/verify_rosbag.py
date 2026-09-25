"""Read a captured ROS bag and check the fail-stop event order."""

import hashlib
import json
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def main():
    directory = Path("/tmp/astra-bag")
    files = sorted(directory.glob("*.db3"))
    if len(files) != 1:
        raise AssertionError(f"expected one SQLite bag, found {len(files)}")
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(directory), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    topic_types = {
        topic.name: topic.type for topic in reader.get_all_topics_and_types()
    }
    events = []
    counts = {}
    while reader.has_next():
        topic, serialized, timestamp = reader.read_next()
        counts[topic] = counts.get(topic, 0) + 1
        if topic not in {
            "/astra/safety/faults",
            "/astra/safety/recovery",
            "/astra/control/authorized_cmd_vel",
            "/astra/goals/decision",
        }:
            continue
        message = deserialize_message(serialized, get_message(topic_types[topic]))
        if topic.endswith("/faults"):
            label = f"fault:{message.severity}:{message.reason}"
        elif topic.endswith("/recovery"):
            label = "recovery" if message.data else "recovery_false"
        elif topic.endswith("/authorized_cmd_vel"):
            label = (
                "motor_nonzero"
                if message.linear.x or message.angular.z
                else "motor_zero"
            )
        else:
            label = f"policy:{message.result_code}"
        events.append((timestamp, label))
    labels = [label for _, label in events]
    required = {
        "motor_nonzero",
        "recovery",
        "policy:OK",
        "policy:APPROVAL_REQUIRED",
        "fault:EMERGENCY:external_estop",
        "fault:PROTECTIVE:invalid_or_unsafe_control_intent",
    }
    missing = required - set(labels)
    if missing:
        raise AssertionError(f"bag missing events: {sorted(missing)}")
    estop_index = labels.index("fault:EMERGENCY:external_estop")
    recovery_index = labels.index("recovery", estop_index)
    if "motor_nonzero" in labels[estop_index + 1 : recovery_index]:
        raise AssertionError("nonzero motor command after E-stop before recovery")
    digest = hashlib.sha256(files[0].read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "bag_sha256": digest,
                "topics": counts,
                "estop_to_recovery_zero_motion": True,
                "policy_and_fault_lineage": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
