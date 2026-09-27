"""Exercise Astra's live skill action against camera/world and goal policy."""

import json
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import (
    ControlIntent,
    EntityState,
    GoalRequest,
    PolicyDecision,
    SafetyState,
    SkillDescriptor,
)
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Bool


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
        self.states = []
        self.commands = []
        self.odometry = []
        self.rgb_frames = 0
        self.depth_frames = 0
        self.keepalive = False
        self.goals = self.create_publisher(GoalRequest, "/astra/goals/request", 4)
        self.arm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.intent = self.create_publisher(ControlIntent, "/astra/control/intent", 4)
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
            SafetyState, "/astra/safety/state", self.states.append, durable
        )
        self.create_subscription(
            Twist, "/astra/control/authorized_cmd_vel", self.on_command, 4
        )
        self.create_subscription(
            Odometry,
            "/astra/sensors/odom",
            self.odometry.append,
            QoSProfile(depth=4, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        sensor_qos = QoSProfile(depth=2, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            Image,
            "/astra/sensors/rgbd/image",
            lambda _image: self.count_rgb(),
            sensor_qos,
        )
        self.create_subscription(
            Image,
            "/astra/sensors/rgbd/depth_image",
            lambda _image: self.count_depth(),
            sensor_qos,
        )
        self.create_subscription(
            SkillDescriptor,
            "/astra/skills/catalog",
            lambda descriptor: self.catalog.add(descriptor.name),
            durable,
        )
        self.action = ActionClient(self, SkillInvocation, "/astra/skills/invoke")
        self.create_timer(0.15, self.refresh_goal)
        self.create_timer(0.05, self.keepalive_zero)

    def on_command(self, command):
        self.commands.append(command)
        if abs(command.linear.x) > 0.02 or abs(command.angular.z) > 0.02:
            self.keepalive = False

    def count_rgb(self):
        self.rgb_frames += 1

    def count_depth(self):
        self.depth_frames += 1

    def keepalive_zero(self):
        if self.keepalive and self.states and self.states[-1].mode == "ACTIVE":
            zero = ControlIntent()
            zero.schema_version = "astra.control-intent.v1"
            zero.mission_id = MISSION
            zero.frame_id = "base_link"
            zero.clock_domain = "sim"
            zero.issued_at = self.states[-1].observed_at
            zero.ttl_seconds = 0.2
            self.intent.publish(zero)

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
        goal.requested_at = (
            self.states[-1].observed_at
            if self.states
            else self.get_clock().now().to_msg()
        )
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
        request.requested_at = (
            self.states[-1].observed_at
            if self.states
            else self.get_clock().now().to_msg()
        )
        request.timeout_seconds = timeout
        accepted = self.action.send_goal_async(request)
        self.until(lambda: accepted.done())
        handle = accepted.result()
        assert handle.accepted, f"{name} rejected"
        finished = handle.get_result_async()
        self.until(lambda: finished.done(), seconds=timeout + 3.0)
        result = finished.result().result
        assert result.completed and result.result_code == "OK", (
            name,
            result.result_code,
            result.reason,
        )
        return result.reason

    def arm_for_motion(self):
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            self.arm.publish(Bool(data=True))
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.states and self.states[-1].mode == "ACTIVE":
                self.keepalive = True
                self.keepalive_zero()
                return
        raise AssertionError("operator arm failed before motion")


def main():
    rclpy.init()
    node = Probe()
    try:
        node.until(lambda: node.action.server_is_ready())
        node.until(lambda: len(node.catalog) == 10)
        try:
            node.until(
                lambda: any(e.entity_id == TARGET for e in node.entities),
                seconds=45,
            )
        except AssertionError as exc:
            raise AssertionError(
                f"RGB-D target absent: rgb_frames={node.rgb_frames} "
                f"depth_frames={node.depth_frames} entities={len(node.entities)}"
            ) from exc
        node.until(
            lambda: node.states
            and node.states[-1].mode == "SAFE_IDLE"
            and any(
                e.entity_id == "obstacle/front" and e.pose.pose.position.x >= 0.8
                for e in node.entities[-30:]
            ),
            seconds=20,
        )
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
        ):
            passed[skill] = node.invoke(skill)
        node.until(lambda: bool(node.odometry))
        node.arm_for_motion()
        passed["navigate_to"] = node.invoke("navigate_to", timeout=20.0)
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE")
        node.arm_for_motion()
        motion_index = len(node.commands)
        passed["align_base"] = node.invoke("align_base", timeout=8.0)
        # A standalone skill caller must explicitly release the base lease.
        node.arm.publish(Bool(data=False))
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE")
        assert any(
            abs(command.angular.z) > 0.02 for command in node.commands[motion_index:]
        ), "alignment did not produce an authorized angular command"
        node.arm_for_motion()
        passed["point_at"] = node.invoke("point_at", timeout=10.0)
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE")
        node.arm_for_motion()
        passed["return_home"] = node.invoke("return_home", timeout=25.0)
        passed["safe_stop"] = node.invoke("safe_stop", timeout=2.0)
        print(json.dumps({"skill_catalog": len(node.catalog), "passed": passed}))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
