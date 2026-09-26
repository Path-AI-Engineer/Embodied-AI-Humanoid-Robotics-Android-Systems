"""Check that raw bag sensors produced new perception and world-model facts."""

import json
import sys
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def main() -> None:
    directory = Path(sys.argv[1])
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(directory), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    expected_topics = {"/astra/perception/percepts", "/astra/world/entities"}
    if not expected_topics <= types.keys():
        raise AssertionError("replay output is missing perception or world topics")
    counts = {topic: {"object-00": 0, "obstacle/front": 0} for topic in expected_topics}
    while reader.has_next():
        topic, serialized, _timestamp = reader.read_next()
        if topic not in expected_topics:
            continue
        message = deserialize_message(serialized, get_message(types[topic]))
        if message.entity_id in counts[topic]:
            counts[topic][message.entity_id] += 1
    if any(value < 1 for group in counts.values() for value in group.values()):
        raise AssertionError(f"sensor-driven facts missing after replay: {counts}")
    print(
        json.dumps(
            {"status": "sensor_replay_verified", "facts": counts}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
