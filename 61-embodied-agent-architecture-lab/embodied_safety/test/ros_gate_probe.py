"""Drive the real ROS safety gateway against Gazebo sensor data."""

import json
import time

import rclpy
from astra_interfaces.msg import (
    ControlIntent,
    EntityState,
    GoalRequest,
    Percept,
    PolicyDecision,
    SafetyState,
)
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


class Probe(Node):
    def __init__(self):
        super().__init__("safety_gateway_probe")
        self.states = []
        self.commands = []
        self.percepts = []
        self.entities = []
        self.decisions = []
        self.arm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.estop = self.create_publisher(Bool, "/astra/safety/estop", 1)
        self.recover = self.create_publisher(Bool, "/astra/safety/recovery", 1)
        self.intent = self.create_publisher(ControlIntent, "/astra/control/intent", 5)
        self.goals = self.create_publisher(GoalRequest, "/astra/goals/request", 4)
        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            SafetyState, "/astra/safety/state", self.states.append, state_qos
        )
        self.create_subscription(
            Twist, "/astra/control/authorized_cmd_vel", self.commands.append, 1
        )
        sensor_qos = QoSProfile(depth=8, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            Percept, "/astra/perception/percepts", self.percepts.append, sensor_qos
        )
        self.create_subscription(
            EntityState, "/astra/world/entities", self.entities.append, 8
        )
        self.create_subscription(
            PolicyDecision, "/astra/goals/decision", self.decisions.append, state_qos
        )

    def until(self, predicate, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if predicate():
                return
        raise AssertionError(
            f"timed out; last state={self.states[-1] if self.states else 'none'}"
        )


def main():
    rclpy.init()
    node = Probe()
    try:
        # Let rosbag discover the probe's otherwise silent command/recovery topics.
        warmup_until = time.monotonic() + 2.0
        while time.monotonic() < warmup_until:
            rclpy.spin_once(node, timeout_sec=0.05)
        node.until(lambda: any(s.mode == "SAFE_IDLE" for s in node.states))
        node.until(lambda: any(p.entity_id == "obstacle/front" for p in node.percepts))
        node.until(lambda: any(e.entity_id == "obstacle/front" for e in node.entities))
        goal = GoalRequest()
        goal.schema_version = "astra.goal-request.v1"
        goal.mission_id = "ros-policy-probe"
        goal.target_id = "object-00"
        goal.station_id = "inspection-station"
        goal.requested_by = "local-operator"
        goal.frame_id = "map"
        goal.clock_domain = "sim"
        goal.requested_at = node.states[-1].observed_at
        goal.ttl_seconds = 0.8
        node.goals.publish(goal)
        node.until(lambda: node.decisions and node.decisions[-1].allowed)
        goal.station_id = "restricted-station"
        goal.approved_restricted_zone = True
        goal.requested_at = node.states[-1].observed_at
        node.goals.publish(goal)
        node.until(
            lambda: node.decisions
            and node.decisions[-1].result_code == "APPROVAL_REQUIRED"
            and not node.decisions[-1].allowed
        )
        node.arm.publish(Bool(data=True))
        node.until(lambda: node.states and node.states[-1].mode == "ACTIVE")
        intent = ControlIntent()
        intent.schema_version = "astra.control-intent.v1"
        intent.mission_id = "ros-gate-probe"
        intent.frame_id = "base_link"
        intent.clock_domain = "sim"
        intent.issued_at = node.states[-1].observed_at
        intent.ttl_seconds = 0.2
        intent.linear_meters_per_second = 0.12
        node.intent.publish(intent)
        node.until(lambda: any(c.linear.x > 0.0 for c in node.commands), 2)
        node.estop.publish(Bool(data=True))
        node.until(
            lambda: node.states
            and node.states[-1].mode == "EMERGENCY_STOP"
            and node.states[-1].estop_latched
        )
        zero_index = len(node.commands)
        node.intent.publish(intent)
        node.until(lambda: len(node.commands) > zero_index)
        assert all(c.linear.x == 0.0 for c in node.commands[zero_index:])
        node.recover.publish(Bool(data=True))
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE")
        node.arm.publish(Bool(data=True))
        node.until(lambda: node.states and node.states[-1].mode == "ACTIVE")
        bad = ControlIntent()
        bad.schema_version = intent.schema_version
        bad.mission_id = intent.mission_id
        bad.frame_id = intent.frame_id
        bad.clock_domain = intent.clock_domain
        bad.issued_at = node.states[-1].observed_at
        bad.ttl_seconds = 0.2
        bad.linear_meters_per_second = 1.0
        node.intent.publish(bad)
        node.until(
            lambda: node.states
            and node.states[-1].mode == "PROTECTIVE_STOP"
            and node.states[-1].reason == "invalid_or_unsafe_control_intent"
        )
        print(
            json.dumps(
                {
                    "sensor_readiness": "verified",
                    "sensor_percept_to_world": "verified",
                    "goal_policy_and_untrusted_approval_rejection": "verified",
                    "bounded_command": "verified",
                    "estop_latch": "verified",
                    "explicit_recovery": "verified",
                    "speed_limit": "verified",
                }
            )
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
