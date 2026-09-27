"""Positive and negative DDS publisher probe for the SROS2 fixture."""

import argparse
import json
import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Twist
from rclpy.action import ActionClient, ActionServer
from rclpy.node import Node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "role",
        choices=(
            "listener",
            "authorized",
            "unauthorized",
            "arm_server",
            "arm_authorized",
            "arm_unauthorized",
        ),
    )
    args, ros_args = parser.parse_known_args()
    name = {
        "listener": "security_listener",
        "authorized": "security_authorized_publisher",
        "unauthorized": "unauthorized_publisher",
        "arm_server": "security_arm_controller",
        "arm_authorized": "security_arm_gateway",
        "arm_unauthorized": "unauthorized_arm_client",
    }[args.role]
    rclpy.init(args=ros_args)
    node = Node(name, start_parameter_services=False, enable_logger_service=False)
    try:
        if args.role == "arm_server":
            seen = []

            def execute(goal_handle):
                seen.append(goal_handle.request.trajectory.joint_names)
                goal_handle.succeed()
                return FollowJointTrajectory.Result()

            server = ActionServer(
                node,
                FollowJointTrajectory,
                "/arm_controller/follow_joint_trajectory",
                execute,
            )
            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)
            server.destroy()
            print(json.dumps({"accepted_arm_goals": len(seen)}), flush=True)
            if len(seen) != 1:
                raise SystemExit(1)
        elif args.role in ("arm_authorized", "arm_unauthorized"):
            try:
                client = ActionClient(
                    node,
                    FollowJointTrajectory,
                    "/arm_controller/follow_joint_trajectory",
                )
            except ValueError as exc:
                if (
                    args.role != "arm_unauthorized"
                    or "Failed to create action client" not in str(exc)
                ):
                    raise
                print(
                    json.dumps(
                        {
                            "unauthorized_arm_goal_accepted": False,
                            "denial": "action_client_construction_denied",
                        }
                    ),
                    flush=True,
                )
                return
            ready = client.wait_for_server(timeout_sec=5.0)
            if args.role == "arm_unauthorized":
                if ready:
                    request = FollowJointTrajectory.Goal()
                    request.trajectory.joint_names = ["arm_joint_1"]
                    future = client.send_goal_async(request)
                    deadline = time.monotonic() + 3.0
                    while not future.done() and time.monotonic() < deadline:
                        rclpy.spin_once(node, timeout_sec=0.1)
                    if future.done() and future.result().accepted:
                        raise SystemExit("unauthorized arm action was accepted")
                print(json.dumps({"unauthorized_arm_goal_accepted": False}), flush=True)
            else:
                if not ready:
                    raise SystemExit("authorized arm client cannot find action server")
                request = FollowJointTrajectory.Goal()
                request.trajectory.joint_names = ["arm_joint_1"]
                future = client.send_goal_async(request)
                deadline = time.monotonic() + 5.0
                while not future.done() and time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=0.1)
                if not future.done() or not future.result().accepted:
                    raise SystemExit("authorized arm action was not accepted")
                result = future.result().get_result_async()
                while not result.done() and time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=0.1)
                if not result.done():
                    raise SystemExit("authorized arm action did not finish")
                print(json.dumps({"authorized_arm_goal_accepted": True}), flush=True)
        elif args.role == "listener":
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
