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
        goal.requested_at = self.states[-1].observed_at
        goal.ttl_seconds = 0.8
        self.goals.publish(goal)

    def operator_arm(self):
        self.arm.publish(Bool(data=True))
        self.zero_heartbeat()

    def zero_heartbeat(self):
        intent = ControlIntent()
        intent.schema_version = "astra.control-intent.v1"
        intent.mission_id = MISSION
        intent.frame_id = "base_link"
        intent.clock_domain = "sim"
        intent.issued_at = self.states[-1].observed_at
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
        next_point_heartbeat = 0.0
        armed_stages = set()
        while (
            time.monotonic() < deadline
            and "SUCCEEDED" not in node.events
            and "ABORTED_SAFE" not in node.events
            and "ABORTED_UNCONFIRMED" not in node.events
        ):
            if "RUNNING" not in node.events and time.monotonic() >= next_goal:
                node.publish_goal()
                next_goal = time.monotonic() + 0.15
            stage = node.events.count("SKILL_OK")
            if (
                stage == 5
                and node.states
                and node.states[-1].mode == "ACTIVE"
                and time.monotonic() >= next_point_heartbeat
            ):
                # Keep the operator's zero-motion lease alive while DDS hands
                # point_at from the executive to the independent arm gateway.
                node.zero_heartbeat()
                next_point_heartbeat = time.monotonic() + 0.08
            if stage in {3, 4, 5, 8} and stage not in armed_stages and node.states:
                if node.states[-1].mode == "SAFE_IDLE":
                    node.operator_arm()
                elif node.states[-1].mode == "ACTIVE":
                    armed_stages.add(stage)
            rclpy.spin_once(node, timeout_sec=0.05)
        assert "RUNNING" in node.events, node.events
        assert node.events.count("SKILL_OK") == 10, (
            f"events={node.events}; "
            f"safety={node.states[-1] if node.states else 'none'}; "
            f"recent_reasons={[state.reason for state in node.states[-30:]]}"
        )
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
