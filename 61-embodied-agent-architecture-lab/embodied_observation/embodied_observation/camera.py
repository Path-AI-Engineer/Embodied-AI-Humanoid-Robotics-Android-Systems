"""Detect the synthetic red fiducial from synchronized RGB-D observations."""

import math
import statistics
import struct

import rclpy
from astra_interfaces.msg import Percept
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


OPTICAL_FRAME = "camera_optical_frame"
RGB_TOPIC = "/astra/sensors/rgbd/image"
DEPTH_TOPIC = "/astra/sensors/rgbd/depth_image"
HORIZONTAL_FOV_RADIANS = 1.047


def stamp_ns(stamp):
    return stamp.sec * 10**9 + stamp.nanosec


def red_centroid(image):
    """Return a pixel centroid only when a sufficiently large red marker exists."""
    if image.encoding != "rgb8" or image.step < image.width * 3:
        return None
    if len(image.data) < image.step * image.height:
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


def marker_depth(depth, x, y):
    if depth.encoding != "32FC1" or depth.step < depth.width * 4:
        return None
    if len(depth.data) < depth.step * depth.height:
        return None
    samples = []
    for row in range(max(0, y - 2), min(depth.height, y + 3)):
        for col in range(max(0, x - 2), min(depth.width, x + 3)):
            offset = row * depth.step + col * 4
            value = struct.unpack_from("<f", depth.data, offset)[0]
            if math.isfinite(value) and 0.1 < value < 8.0:
                samples.append(value)
    return statistics.median(samples) if len(samples) >= 5 else None


class CameraPerception(LifecycleNode):
    def __init__(self):
        super().__init__("camera_perception")
        self.active = False
        self.latest_depth = None
        sensor_qos = QoSProfile(depth=3, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.publisher = self.create_lifecycle_publisher(
            Percept, "/astra/perception/percepts", sensor_qos
        )
        self.depth_subscription = self.create_subscription(
            Image, DEPTH_TOPIC, self.on_depth, sensor_qos
        )
        self.rgb_subscription = self.create_subscription(
            Image, RGB_TOPIC, self.on_rgb, sensor_qos
        )

    def on_configure(self, state):
        self.latest_depth = None
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        self.active = True
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.active = False
        self.latest_depth = None
        return super().on_deactivate(state)

    def on_depth(self, image):
        if self.active and image.header.frame_id == OPTICAL_FRAME:
            self.latest_depth = image

    def on_rgb(self, image):
        if not self.active or image.header.frame_id != OPTICAL_FRAME:
            return
        depth = self.latest_depth
        if depth is None or depth.width != image.width or depth.height != image.height:
            return
        observed_ns = stamp_ns(image.header.stamp)
        age = (self.get_clock().now().nanoseconds - observed_ns) / 10**9
        depth_delta = abs(observed_ns - stamp_ns(depth.header.stamp)) / 10**9
        if not -0.05 <= age <= 0.25 or depth_delta > 0.10:
            return
        centroid = red_centroid(image)
        if centroid is None:
            return
        count, x, y = centroid
        range_m = marker_depth(depth, x, y)
        if range_m is None:
            return
        focal_pixels = image.width / (2 * math.tan(HORIZONTAL_FOV_RADIANS / 2))
        percept = Percept()
        percept.schema_version = "astra.percept.v1"
        percept.entity_id = "object-00"
        percept.source_topic = RGB_TOPIC
        percept.frame_id = OPTICAL_FRAME
        percept.clock_domain = "sim"
        percept.observed_at = image.header.stamp
        percept.ttl_seconds = 0.25
        percept.confidence = min(0.99, 0.8 + count / 5000)
        percept.pose.pose.position.x = (x - image.width / 2) * range_m / focal_pixels
        percept.pose.pose.position.y = (y - image.height / 2) * range_m / focal_pixels
        percept.pose.pose.position.z = range_m
        percept.pose.pose.orientation.w = 1.0
        percept.pose.covariance[0] = 0.01
        percept.pose.covariance[7] = 0.01
        percept.pose.covariance[14] = 0.04
        percept.result_code = "OK"
        self.publisher.publish(percept)


def main():
    rclpy.init()
    node = CameraPerception()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
