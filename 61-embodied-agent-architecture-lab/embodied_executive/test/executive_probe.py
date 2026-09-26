"""Verify a real mission aborts safely at the uncommissioned navigation adapter."""

import json
import time

import rclpy
from astra_interfaces.msg import ControlIntent, GoalRequest, SafetyState
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String


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
        self.arm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.intent = self.create_publisher(ControlIntent, "/astra/control/intent", 4)
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

    def operator_arm(self):
        self.arm.publish(Bool(data=True))
        intent = ControlIntent()
        intent.schema_version = "astra.control-intent.v1"
        intent.mission_id = MISSION
        intent.frame_id = "base_link"
        intent.clock_domain = "sim"
        intent.issued_at = self.get_clock().now().to_msg()
        intent.ttl_seconds = 0.2
        self.intent.publish(intent)


def main():
    rclpy.init()
    node = Probe()
    try:
        ready_deadline = time.monotonic() + 10
        while time.monotonic() < ready_deadline and not node.states:
            rclpy.spin_once(node, timeout_sec=0.05)
        assert node.states, "safety state publisher not discovered"
        deadline = time.monotonic() + 90
        next_goal = 0.0
        while time.monotonic() < deadline and "SUCCEEDED" not in node.events:
            if "RUNNING" not in node.events and time.monotonic() >= next_goal:
                node.publish_goal()
                next_goal = time.monotonic() + 0.15
            if (
                node.events.count("SKILL_OK") in {3, 4, 5, 8}
                and node.states
                and node.states[-1].mode == "SAFE_IDLE"
            ):
                node.operator_arm()
            rclpy.spin_once(node, timeout_sec=0.05)
        assert "RUNNING" in node.events, node.events
        assert node.events.count("SKILL_OK") == 10, node.events
        assert "SKILL_FAILED" not in node.events, node.events
        assert node.events[-1] == "SUCCEEDED", node.events
        safe_deadline = time.monotonic() + 3
        while time.monotonic() < safe_deadline and node.states[-1].mode == "ACTIVE":
            rclpy.spin_once(node, timeout_sec=0.05)
        assert node.states[-1].mode != "ACTIVE", node.states[-1:]
        assert any(
            abs(command.linear.x) > 0.02 or abs(command.angular.z) > 0.02
            for command in node.commands
        ), "mission never moved under authorization"
        assert node.commands[-1].linear.x == 0 and node.commands[-1].angular.z == 0
        print(json.dumps({"mission": MISSION, "events": node.events, "safe": True}))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
