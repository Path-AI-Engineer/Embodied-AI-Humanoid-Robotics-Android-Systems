"""Compare source/replay facts at shared source timestamps, without hiding drops."""

import json
import sys
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


EXPECTED_TOPICS = {"/astra/perception/percepts", "/astra/world/entities"}
EXPECTED_ENTITIES = {"object-00", "obstacle/front"}


def read_facts(
    directory: Path,
) -> dict[str, dict[tuple[str, int, int], tuple[object, ...]]]:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(directory), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    if not EXPECTED_TOPICS <= types.keys():
        raise AssertionError("replay output is missing perception or world topics")
    facts: dict[str, dict[tuple[str, int, int], tuple[object, ...]]] = {
        topic: {} for topic in EXPECTED_TOPICS
    }
    while reader.has_next():
        topic, serialized, _timestamp = reader.read_next()
        if topic not in EXPECTED_TOPICS:
            continue
        message = deserialize_message(serialized, get_message(types[topic]))
        if message.entity_id not in EXPECTED_ENTITIES:
            continue
        key = (
            message.entity_id,
            message.observed_at.sec,
            message.observed_at.nanosec,
        )
        pose = message.pose.pose
        signature = (
            message.schema_version,
            message.frame_id,
            message.clock_domain,
            message.source_topic if topic.endswith("percepts") else message.provenance,
            round(message.confidence, 7),
            round(pose.position.x, 7),
            round(pose.position.y, 7),
            round(pose.position.z, 7),
            message.ttl_seconds
            if topic.endswith("percepts")
            else message.valid_until.sec,
            0 if topic.endswith("percepts") else message.valid_until.nanosec,
        )
        prior = facts[topic].setdefault(key, signature)
        if prior != signature:
            raise AssertionError(f"conflicting facts at one source timestamp: {key}")
    return facts


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_sensor_replay.py ORIGINAL_BAG REPLAY_BAG")
    original = read_facts(Path(sys.argv[1]))
    replay = read_facts(Path(sys.argv[2]))
    comparison = {}
    for topic in sorted(EXPECTED_TOPICS):
        source_facts = original[topic]
        replay_facts = replay[topic]
        common = source_facts.keys() & replay_facts.keys()
        if len(common) < 20:
            raise AssertionError(f"insufficient shared sensor timestamps: {topic}")
        mismatches = [key for key in common if source_facts[key] != replay_facts[key]]
        if mismatches:
            raise AssertionError(f"replayed facts diverged: {topic}: {mismatches[:3]}")
        by_entity = {
            entity: sum(key[0] == entity for key in common)
            for entity in sorted(EXPECTED_ENTITIES)
        }
        if any(value < 1 for value in by_entity.values()):
            raise AssertionError(f"sensor-derived entity missing: {topic}: {by_entity}")
        comparison[topic] = {
            "source_unique": len(source_facts),
            "replay_unique": len(replay_facts),
            "matching_source_timestamps": len(common),
            "source_only": len(source_facts) - len(common),
            "replay_only": len(replay_facts) - len(common),
            "source_coverage": round(len(common) / len(source_facts), 4),
            "replay_coverage": round(len(common) / len(replay_facts), 4),
            "exact_set_equivalent": source_facts == replay_facts,
            "by_entity": by_entity,
        }
    print(
        json.dumps(
            {"status": "overlapping_sensor_facts_equivalent", "facts": comparison},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
