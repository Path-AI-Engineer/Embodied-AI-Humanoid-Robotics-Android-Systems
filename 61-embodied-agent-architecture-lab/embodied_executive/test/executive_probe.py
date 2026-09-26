"""Verify a real mission aborts safely at the uncommissioned navigation adapter."""

import json
import time

import rclpy
from astra_interfaces.msg import GoalRequest, SafetyState
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


MISSION = "mission-ros-probe"


class Probe(Node):
    def __init__(self):
        super().__init__(
            "mission_executive_probe",
            parameter_overrides=[Parameter("use_sim_time", value=True)],
        )
        self.events = []
        self.states = []
        self.commands = []
        self.goals = self.create_publisher(GoalRequest, "/astra/goals/request", 4)
        self.create_subscription(
            String, "/astra/evidence/mission_events", self.on_event, 16
        )
        self.create_subscription(
            SafetyState,
            "/astra/safety/state",
            self.states.append,
            QoSProfile(
                depth=12,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
        self.create_subscription(
            Twist,
            "/astra/control/authorized_cmd_vel",
            self.commands.append,
            4,
        )

    def on_event(self, message):
        event = json.loads(message.data)
        if event["mission_id"] == MISSION:
            self.events.append(event["status"])

    def publish_goal(self):
        goal = GoalRequest()
        goal.schema_version = "astra.goal-request.v1"
        goal.mission_id = MISSION
        goal.target_id = "object-00"
        goal.station_id = "inspection-station"
        goal.requested_by = "local-operator"
        goal.frame_id = "map"
        goal.clock_domain = "sim"
        goal.requested_at = self.get_clock().now().to_msg()
        goal.ttl_seconds = 0.8
        self.goals.publish(goal)


def main():
    rclpy.init()
    node = Probe()
    try:
        deadline = time.monotonic() + 45
        next_goal = 0.0
        while time.monotonic() < deadline and "ABORTED_SAFE" not in node.events:
            if "RUNNING" not in node.events and time.monotonic() >= next_goal:
                node.publish_goal()
                next_goal = time.monotonic() + 0.15
            rclpy.spin_once(node, timeout_sec=0.05)
        assert "RUNNING" in node.events, node.events
        assert node.events.count("SKILL_OK") == 3, node.events
        assert "SKILL_FAILED" in node.events, node.events
        assert node.events[-1] == "ABORTED_SAFE", node.events
        assert "SUCCEEDED" not in node.events, node.events
        assert node.states and node.states[-1].mode != "ACTIVE", node.states[-1:]
        assert all(
            command.linear.x == 0 and command.angular.z == 0
            for command in node.commands
        ), node.commands
        print(json.dumps({"mission": MISSION, "events": node.events, "safe": True}))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
