"""Publish conservative front-obstacle percepts from lidar, never Gazebo truth."""

import math

import rclpy
from astra_interfaces.msg import Percept
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class LidarPerception(LifecycleNode):
    def __init__(self):
        super().__init__("lidar_perception")
        self.active = False
        sensor_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        percept_qos = QoSProfile(depth=8, reliability=ReliabilityPolicy.RELIABLE)
        self.publisher = self.create_lifecycle_publisher(
            Percept, "/astra/perception/percepts", percept_qos
        )
        self.world_publisher = self.create_lifecycle_publisher(
            Percept, "/astra/perception/lidar", percept_qos
        )
        self.subscription = self.create_subscription(
            LaserScan, "/astra/sensors/scan", self.on_scan, sensor_qos
        )

    def on_configure(self, state):
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        self.active = True
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.active = False
        return super().on_deactivate(state)

    def on_scan(self, scan):
        if not self.active:
            return
        if scan.header.frame_id != "astra/base_footprint/lidar_2d":
            return
        age = (
            self.get_clock().now().nanoseconds
            - (scan.header.stamp.sec * 10**9 + scan.header.stamp.nanosec)
        ) / 10**9
        # /clock and LaserScan use independent DDS streams; a small apparent
        # future timestamp is transport ordering, not a different clock domain.
        if not -0.05 <= age <= 0.25 or scan.angle_increment <= 0:
            return
        candidates = [
            (distance, scan.angle_min + index * scan.angle_increment)
            for index, distance in enumerate(scan.ranges)
            if abs(scan.angle_min + index * scan.angle_increment) <= 0.65
            and math.isfinite(distance)
            and scan.range_min <= distance <= scan.range_max
        ]
        if not candidates:
            return
        distance, angle = min(candidates)
        percept = Percept()
        percept.schema_version = "astra.percept.v1"
        percept.entity_id = "obstacle/front"
        percept.source_topic = "/astra/sensors/scan"
        percept.frame_id = scan.header.frame_id
        percept.clock_domain = "sim"
        percept.observed_at = scan.header.stamp
        percept.ttl_seconds = 0.25
        percept.confidence = 0.8
        percept.pose.pose.position.x = distance * math.cos(angle)
        percept.pose.pose.position.y = distance * math.sin(angle)
        percept.pose.pose.orientation.w = 1.0
        percept.pose.covariance[0] = 0.04
        percept.pose.covariance[7] = 0.04
        percept.result_code = "OK"
        self.publisher.publish(percept)
        self.world_publisher.publish(percept)


def main():
    rclpy.init()
    node = LidarPerception()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
