"""Check the synthetic target is observable through ROS images, not Gazebo truth."""

import json
import math
import os
import struct
import time
import zlib
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


def red_centroid(image):
    if image.encoding != "rgb8" or image.step < image.width * 3:
        return None
    view = memoryview(image.data)
    count = sum_x = sum_y = 0
    for y in range(0, image.height, 2):
        for x in range(0, image.width, 2):
            offset = y * image.step + x * 3
            red, green, blue = view[offset : offset + 3]
            if red > 150 and green < 80 and blue < 80 and red > 2 * green:
                count += 1
                sum_x += x
                sum_y += y
    if count < 20:
        return None
    return count, round(sum_x / count), round(sum_y / count)


def save_debug_png(image, destination):
    if image.encoding != "rgb8":
        return
    rows = b"".join(
        b"\x00" + bytes(image.data[y * image.step : y * image.step + image.width * 3])
        for y in range(image.height)
    )

    def chunk(kind, payload):
        body = kind + payload
        return (
            struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(
        b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    )
    png += chunk(b"IDAT", zlib.compress(rows))
    png += chunk(b"IEND", b"")
    Path(destination).write_bytes(png)


class CameraProbe(Node):
    def __init__(self):
        super().__init__("camera_contract_probe")
        qos = QoSProfile(depth=4, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.latest_rgb = None
        self.latest_depth = None
        self.create_subscription(Image, "/astra/sensors/rgbd/image", self.on_rgb, qos)
        self.create_subscription(
            Image, "/astra/sensors/rgbd/depth_image", self.on_depth, qos
        )

    def on_rgb(self, image):
        self.latest_rgb = image

    def on_depth(self, image):
        self.latest_depth = image


def main():
    rclpy.init()
    node = CameraProbe()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            rgb, depth = node.latest_rgb, node.latest_depth
            if rgb is None or depth is None:
                continue
            centroid = red_centroid(rgb)
            if centroid is None or depth.encoding != "32FC1":
                continue
            count, x, y = centroid
            offset = y * depth.step + x * 4
            range_m = struct.unpack_from("<f", depth.data, offset)[0]
            if not math.isfinite(range_m) or not 0.1 < range_m < 8:
                continue
            result = {
                "red_samples": count,
                "rgb_frame": rgb.header.frame_id,
                "depth_frame": depth.header.frame_id,
                "depth_m": round(range_m, 3),
                "rgb_encoding": rgb.encoding,
                "depth_encoding": depth.encoding,
            }
            print(json.dumps(result), flush=True)
            if rgb.header.frame_id != "camera_optical_frame":
                raise AssertionError("camera frame is not in the Astra TF tree")
            if depth.header.frame_id != rgb.header.frame_id:
                raise AssertionError("RGB and depth use different frames")
            return
        debug_path = os.getenv("ASTRA_CAMERA_DEBUG_PATH")
        if debug_path and node.latest_rgb:
            save_debug_png(node.latest_rgb, debug_path)
        raise AssertionError(
            f"no target RGB-D frame: rgb={node.latest_rgb is not None}, "
            f"depth={node.latest_depth is not None}, "
            f"centroid={red_centroid(node.latest_rgb) if node.latest_rgb else None}"
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
