"""Exercise Astra's live skill action against camera/world and goal policy."""

import json
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import (
    EntityState,
    GoalRequest,
    PolicyDecision,
    SkillDescriptor,
)
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


MISSION = "ros-skill-probe"
TARGET = "object-00"


class Probe(Node):
    def __init__(self):
        super().__init__(
            "skill_action_probe",
            parameter_overrides=[Parameter("use_sim_time", value=True)],
        )
        self.entities = []
        self.decisions = []
        self.catalog = set()
        self.goals = self.create_publisher(GoalRequest, "/astra/goals/request", 4)
        durable = QoSProfile(
            depth=12,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            EntityState, "/astra/world/entities", self.entities.append, 8
        )
        self.create_subscription(
            PolicyDecision, "/astra/goals/decision", self.decisions.append, durable
        )
        self.create_subscription(
            SkillDescriptor,
            "/astra/skills/catalog",
            lambda descriptor: self.catalog.add(descriptor.name),
            durable,
        )
        self.action = ActionClient(self, SkillInvocation, "/astra/skills/invoke")
        self.create_timer(0.15, self.refresh_goal)

    def refresh_goal(self):
        if self.get_clock().now().nanoseconds == 0:
            return
        goal = GoalRequest()
        goal.schema_version = "astra.goal-request.v1"
        goal.mission_id = MISSION
        goal.target_id = TARGET
        goal.station_id = "inspection-station"
        goal.requested_by = "local-operator"
        goal.frame_id = "map"
        goal.clock_domain = "sim"
        goal.requested_at = self.get_clock().now().to_msg()
        goal.ttl_seconds = 0.8
        self.goals.publish(goal)

    def until(self, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if predicate():
                return
        raise AssertionError("live skill prerequisite or action timed out")

    def invoke(self, name, timeout=5.0):
        request = SkillInvocation.Goal()
        request.schema_version = "astra.skill-invocation.v1"
        request.mission_id = MISSION
        request.skill_name = name
        request.target_id = TARGET
        request.frame_id = "map"
        request.clock_domain = "sim"
        request.requested_at = self.get_clock().now().to_msg()
        request.timeout_seconds = timeout
        accepted = self.action.send_goal_async(request)
        self.until(lambda: accepted.done())
        handle = accepted.result()
        assert handle.accepted, f"{name} rejected"
        finished = handle.get_result_async()
        self.until(lambda: finished.done())
        result = finished.result().result
        assert result.completed and result.result_code == "OK", (
            name,
            result.result_code,
            result.reason,
        )
        return result.reason


def main():
    rclpy.init()
    node = Probe()
    try:
        node.until(lambda: node.action.server_is_ready())
        node.until(lambda: len(node.catalog) == 10)
        node.until(lambda: any(e.entity_id == TARGET for e in node.entities))
        node.until(
            lambda: any(d.mission_id == MISSION and d.allowed for d in node.decisions)
        )
        passed = {}
        for skill in (
            "observe_area",
            "locate_entity",
            "wait_for_clearance",
            "inspect_entity",
            "speak_report",
            "safe_stop",
        ):
            passed[skill] = node.invoke(
                skill, timeout=2.0 if skill == "safe_stop" else 5.0
            )
        print(json.dumps({"skill_catalog": len(node.catalog), "passed": passed}))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
