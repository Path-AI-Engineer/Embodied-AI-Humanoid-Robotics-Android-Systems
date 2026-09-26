"""Validate typed goals before any skill or control path can see them."""

import re

import rclpy
from astra_interfaces.msg import GoalRequest, PolicyDecision
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


TARGET = re.compile(r"^object-[0-9]{2}$")
MISSION = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


class GoalGateway(Node):
    def __init__(self):
        super().__init__("goal_gateway")
        decision_qos = QoSProfile(
            depth=4,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.decisions = self.create_publisher(
            PolicyDecision, "/astra/goals/decision", decision_qos
        )
        self.goals = self.create_subscription(
            GoalRequest, "/astra/goals/request", self.on_goal, 4
        )

    def on_goal(self, goal):
        decision = PolicyDecision()
        decision.schema_version = "astra.policy-decision.v1"
        decision.mission_id = goal.mission_id
        decision.frame_id = "map"
        decision.clock_domain = "sim"
        decision.decided_at = self.get_clock().now().to_msg()
        decision.result_code = "POLICY_DENIED"
        decision.reason = "invalid_goal_contract"
        requested_ns = goal.requested_at.sec * 10**9 + goal.requested_at.nanosec
        age = (self.get_clock().now().nanoseconds - requested_ns) / 10**9
        if (
            goal.schema_version == "astra.goal-request.v1"
            and MISSION.fullmatch(goal.mission_id)
            and TARGET.fullmatch(goal.target_id)
            and goal.requested_by == "local-operator"
            and goal.frame_id == "map"
            and goal.clock_domain == "sim"
            and 0 < goal.ttl_seconds <= 1.0
            and -0.05 <= age <= goal.ttl_seconds
        ):
            if goal.station_id == "inspection-station":
                decision.allowed = True
                decision.result_code = "OK"
                decision.reason = "allowlisted_fixture_mission"
            elif goal.station_id == "restricted-station":
                decision.result_code = "APPROVAL_REQUIRED"
                decision.reason = "unsigned_goal_approval_is_not_authorization"
        self.decisions.publish(decision)


def main():
    rclpy.init()
    node = GoalGateway()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
