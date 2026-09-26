"""Drive the real ROS safety gateway against Gazebo sensor data."""

import json
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import (
    ControlIntent,
    EntityState,
    GoalRequest,
    Percept,
    PolicyDecision,
    SafetyState,
)
from geometry_msgs.msg import Twist
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


class Probe(Node):
    def __init__(self):
        super().__init__(
            "safety_gateway_probe",
            parameter_overrides=[Parameter("use_sim_time", value=True)],
        )
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
        self.arm_action = ActionClient(self, SkillInvocation, "/astra/control/point_at")
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
            f"timed out; last state={self.states[-1] if self.states else 'none'}; "
            f"percepts={len(self.percepts)}; entities={len(self.entities)}; "
            f"decisions={len(self.decisions)}"
        )


def arm_with_fresh_policy(node, goal):
    """Retry the asynchronous goal/arm handshake without bypassing the gateway."""
    deadline = time.monotonic() + 8.0
    next_request = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_request and node.states:
            goal.requested_at = node.states[-1].observed_at
            node.goals.publish(goal)
            node.arm.publish(Bool(data=True))
            next_request = now + 0.2
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.states and node.states[-1].mode == "ACTIVE":
            return
    raise AssertionError(
        "goal/arm handshake timed out; "
        f"state={node.states[-1] if node.states else 'none'}; "
        f"decision={node.decisions[-1] if node.decisions else 'none'}"
    )


def request_decision(node, goal, expected):
    """Wait for the goal gateway to discover the publisher and decide."""
    prior_decisions = len(node.decisions)
    deadline = time.monotonic() + 8.0
    next_request = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_request and node.states:
            goal.requested_at = node.states[-1].observed_at
            node.goals.publish(goal)
            next_request = now + 0.2
        rclpy.spin_once(node, timeout_sec=0.05)
        if len(node.decisions) > prior_decisions and expected(node.decisions[-1]):
            return
    raise AssertionError(
        "goal decision timed out; "
        f"decision={node.decisions[-1] if node.decisions else 'none'}"
    )


def send_fresh_intent(node, intent):
    intent.issued_at = node.get_clock().now().to_msg()
    node.intent.publish(intent)


def wait_for_bounded_command(node, intent):
    """Use the gateway's observed sim clock to keep a bounded intent fresh."""
    deadline = time.monotonic() + 2.0
    last_state_stamp = None
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.02)
        if node.states and node.states[-1].mode == "ACTIVE":
            stamp = node.states[-1].observed_at
            stamp_key = (stamp.sec, stamp.nanosec)
            if stamp_key != last_state_stamp:
                intent.issued_at = stamp
                node.intent.publish(intent)
                last_state_stamp = stamp_key
        if any(command.linear.x > 0.0 for command in node.commands):
            return
    raise AssertionError(
        "bounded command timed out; "
        f"last state={node.states[-1] if node.states else 'none'}"
    )


def main():
    rclpy.init()
    node = Probe()
    try:
        # Let rosbag discover the probe's otherwise silent command/recovery topics.
        warmup_until = time.monotonic() + 2.0
        while time.monotonic() < warmup_until:
            rclpy.spin_once(node, timeout_sec=0.05)
        node.until(
            lambda: node.recover.get_subscription_count() >= 2,
            seconds=12,
        )
        node.until(lambda: any(s.mode == "SAFE_IDLE" for s in node.states))
        node.until(lambda: any(p.entity_id == "obstacle/front" for p in node.percepts))
        node.until(lambda: any(e.entity_id == "obstacle/front" for e in node.entities))
        node.until(lambda: any(p.entity_id == "object-00" for p in node.percepts))
        node.until(lambda: any(e.entity_id == "object-00" for e in node.entities))
        target = next(e for e in node.entities if e.entity_id == "object-00")
        target_lifetime = (
            target.valid_until.sec
            + target.valid_until.nanosec / 10**9
            - target.observed_at.sec
            - target.observed_at.nanosec / 10**9
        )
        assert 0.49 <= target_lifetime <= 0.51, target_lifetime
        node.until(lambda: node.arm_action.server_is_ready())
        unauthorized = SkillInvocation.Goal()
        unauthorized.schema_version = "astra.skill-invocation.v1"
        unauthorized.mission_id = "unauthorized-probe"
        unauthorized.skill_name = "point_at"
        unauthorized.target_id = "object-00"
        unauthorized.frame_id = "map"
        unauthorized.clock_domain = "sim"
        unauthorized.requested_at = node.get_clock().now().to_msg()
        unauthorized.timeout_seconds = 3.0
        unauthorized_sent = node.arm_action.send_goal_async(unauthorized)
        node.until(lambda: unauthorized_sent.done())
        unauthorized_handle = unauthorized_sent.result()
        assert not unauthorized_handle.accepted, "unapproved arm action was admitted"
        node.arm.publish(Bool(data=True))
        for _ in range(5):
            rclpy.spin_once(node, timeout_sec=0.05)
        assert node.states[-1].mode == "SAFE_IDLE", "arm bypassed policy"
        goal = GoalRequest()
        goal.schema_version = "astra.goal-request.v1"
        goal.mission_id = "ros-policy-probe"
        goal.target_id = "object-00"
        goal.station_id = "inspection-station"
        goal.requested_by = "local-operator"
        goal.frame_id = "map"
        goal.clock_domain = "sim"
        goal.ttl_seconds = 0.8
        request_decision(node, goal, lambda decision: decision.allowed)
        goal.station_id = "restricted-station"
        goal.approved_restricted_zone = True
        request_decision(
            node,
            goal,
            lambda decision: decision.result_code == "APPROVAL_REQUIRED"
            and not decision.allowed,
        )
        goal.station_id = "inspection-station"
        goal.approved_restricted_zone = False
        request_decision(node, goal, lambda decision: decision.allowed)
        arm_with_fresh_policy(node, goal)
        intent = ControlIntent()
        intent.schema_version = "astra.control-intent.v1"
        intent.mission_id = goal.mission_id
        intent.frame_id = "base_link"
        intent.clock_domain = "sim"
        intent.ttl_seconds = 0.2
        intent.linear_meters_per_second = 0.12
        wait_for_bounded_command(node, intent)
        node.estop.publish(Bool(data=True))
        node.until(
            lambda: node.states
            and node.states[-1].mode == "EMERGENCY_STOP"
            and node.states[-1].estop_latched
        )
        zero_index = len(node.commands)
        send_fresh_intent(node, intent)
        node.until(lambda: len(node.commands) > zero_index)
        assert all(c.linear.x == 0.0 for c in node.commands[zero_index:])
        node.recover.publish(Bool(data=True))
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE")
        request_decision(node, goal, lambda decision: decision.allowed)
        arm_with_fresh_policy(node, goal)
        bad = ControlIntent()
        bad.schema_version = intent.schema_version
        bad.mission_id = intent.mission_id
        bad.frame_id = intent.frame_id
        bad.clock_domain = intent.clock_domain
        bad.ttl_seconds = 0.2
        bad.linear_meters_per_second = 1.0
        send_fresh_intent(node, bad)
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
                    "rgbd_target_to_world": "verified",
                    "goal_policy_and_untrusted_approval_rejection": "verified",
                    "bounded_command": "verified",
                    "estop_latch": "verified",
                    "explicit_recovery": "verified",
                    "speed_limit": "verified",
                    "arm_gateway_policy_bypass": "rejected",
                }
            )
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
