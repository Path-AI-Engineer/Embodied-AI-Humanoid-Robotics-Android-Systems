"""Positive and negative DDS publisher probe for the SROS2 fixture."""

import argparse
import json
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("listener", "authorized", "unauthorized"))
    args, ros_args = parser.parse_known_args()
    name = {
        "listener": "security_listener",
        "authorized": "security_authorized_publisher",
        "unauthorized": "unauthorized_publisher",
    }[args.role]
    rclpy.init(args=ros_args)
    node = Node(name, start_parameter_services=False, enable_logger_service=False)
    try:
        if args.role == "listener":
            observed = []
            node.create_subscription(
                Twist,
                "/astra/control/authorized_cmd_vel",
                lambda msg: observed.append(msg.linear.x),
                10,
            )
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)
            result = {
                "authorized_seen": any(abs(v - 0.12) < 0.001 for v in observed),
                "unauthorized_seen": any(abs(v - 0.27) < 0.001 for v in observed),
            }
            print(json.dumps(result), flush=True)
            if not result["authorized_seen"] or result["unauthorized_seen"]:
                raise SystemExit(1)
        else:
            publisher = node.create_publisher(
                Twist, "/astra/control/authorized_cmd_vel", 10
            )
            value = 0.12 if args.role == "authorized" else 0.27
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                msg = Twist()
                msg.linear.x = value
                publisher.publish(msg)
                rclpy.spin_once(node, timeout_sec=0.05)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
