"""Publish conservative front-obstacle percepts from lidar, never Gazebo truth."""

import math

import rclpy
from astra_interfaces.msg import Percept
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class LidarPerception(Node):
    def __init__(self):
        super().__init__("lidar_perception")
        sensor_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        percept_qos = QoSProfile(depth=8, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.publisher = self.create_publisher(
            Percept, "/astra/perception/percepts", percept_qos
        )
        self.subscription = self.create_subscription(
            LaserScan, "/astra/sensors/scan", self.on_scan, sensor_qos
        )

    def on_scan(self, scan):
        if scan.header.frame_id != "astra/base_footprint/lidar_2d":
            return
        age = (
            self.get_clock().now().nanoseconds
            - (scan.header.stamp.sec * 10**9 + scan.header.stamp.nanosec)
        ) / 10**9
        if not 0 <= age <= 0.25 or scan.angle_increment <= 0:
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


def main():
    rclpy.init()
    node = LidarPerception()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
