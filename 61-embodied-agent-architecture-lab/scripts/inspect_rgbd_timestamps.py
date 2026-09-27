"""Report RGB/depth source-stamp alignment from a retained ROS bag."""

import bisect
import json
import sys

import rosbag2_py
from embodied_observation.camera import marker_depth, red_centroid
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Image


def main() -> None:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    stamps = {"rgb": [], "depth": []}
    arrival = {"rgb": {}, "depth": {}}
    pending = {"rgb": set(), "depth": set()}
    pending_images = {"rgb": {}, "depth": {}}
    paired_in_record_order = 0
    valid_red_centroids = 0
    valid_exact_depths = 0
    while reader.has_next():
        topic, serialized, _timestamp = reader.read_next()
        if topic not in (
            "/astra/sensors/rgbd/image",
            "/astra/sensors/rgbd/depth_image",
        ):
            continue
        message = deserialize_message(serialized, Image)
        stamp = message.header.stamp.sec * 10**9 + message.header.stamp.nanosec
        kind = "rgb" if topic.endswith("/image") else "depth"
        other = "depth" if kind == "rgb" else "rgb"
        stamps[kind].append(stamp)
        arrival[kind][stamp] = _timestamp
        if stamp in pending[other]:
            pending[other].remove(stamp)
            paired_in_record_order += 1
            other_image = pending_images[other].pop(stamp)
            rgb, depth = (
                (message, other_image) if kind == "rgb" else (other_image, message)
            )
            centroid = red_centroid(rgb)
            if centroid is not None:
                valid_red_centroids += 1
                if marker_depth(depth, centroid[1], centroid[2]) is not None:
                    valid_exact_depths += 1
        else:
            pending[kind].add(stamp)
            pending_images[kind][stamp] = message
            pending[kind] = set(sorted(pending[kind])[-8:])
            pending_images[kind] = {
                key: pending_images[kind][key] for key in pending[kind]
            }
    depths = sorted(stamps["depth"])
    nearest = []
    examples = []
    for stamp in stamps["rgb"]:
        index = bisect.bisect_left(depths, stamp)
        options = depths[max(index - 1, 0) : min(index + 1, len(depths))]
        if not options:
            continue
        delta = min(abs(value - stamp) for value in options)
        nearest.append(delta)
        if len(examples) < 8:
            examples.append(delta)
    paired_arrival_deltas = sorted(
        abs(arrival["rgb"][stamp] - arrival["depth"][stamp])
        for stamp in arrival["rgb"].keys() & arrival["depth"].keys()
    )
    print(
        json.dumps(
            {
                "rgb": len(stamps["rgb"]),
                "depth": len(depths),
                "exact": sum(delta == 0 for delta in nearest),
                "within_10ms": sum(delta <= 10_000_000 for delta in nearest),
                "within_100ms": sum(delta <= 100_000_000 for delta in nearest),
                "paired_with_eight_frame_buffer": paired_in_record_order,
                "valid_red_centroids": valid_red_centroids,
                "valid_exact_depths": valid_exact_depths,
                "exact_pair_arrival_delta_ms_p50": round(
                    paired_arrival_deltas[len(paired_arrival_deltas) // 2] / 1e6, 3
                ),
                "exact_pair_arrival_delta_ms_p99": round(
                    paired_arrival_deltas[int(len(paired_arrival_deltas) * 0.99)] / 1e6,
                    3,
                ),
                "nearest_delta_ns_examples": examples,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
