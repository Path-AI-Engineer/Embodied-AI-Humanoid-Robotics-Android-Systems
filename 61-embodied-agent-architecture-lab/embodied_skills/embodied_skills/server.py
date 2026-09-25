"""ROS action boundary for typed, bounded Astra skill invocations."""

import json
import math
import re
import threading
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import (
    ControlIntent,
    EntityState,
    PolicyDecision,
    SafetyState,
    SkillDescriptor,
    SkillFeedback,
)
from nav_msgs.msg import Odometry
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_msgs.msg import Bool

from .registry import SKILLS


MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
TARGET_ID = re.compile(r"^object-[0-9]{2}$")
STOP_MODES = {"PROTECTIVE_STOP", "EMERGENCY_STOP", "RECOVERY_REQUIRED"}
CACHEABLE = {"inspect_entity", "speak_report"}


class SkillServer(Node):
    def __init__(self):
        super().__init__("skill_server")
        self.lock = threading.RLock()
        self.policy = None
        self.policy_wall = 0.0
        self.safety = None
        self.safety_wall = 0.0
        self.entities = {}
        self.odom = None
        self.odom_wall = 0.0
        self.odom_diagnostic_logged = False
        self.inspected = set()
        self.completed = {}
        self.running = set()
        callbacks = ReentrantCallbackGroup()
        catalog_qos = QoSProfile(
            depth=12,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        decision_qos = QoSProfile(
            depth=4,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.catalog = self.create_publisher(
            SkillDescriptor, "/astra/skills/catalog", catalog_qos
        )
        self.feedback_pub = self.create_publisher(
            SkillFeedback, "/astra/skills/feedback", 8
        )
        self.intent = self.create_publisher(ControlIntent, "/astra/control/intent", 5)
        self.disarm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.speech = self.create_publisher(String, "/astra/skills/spoken_report", 4)
        self.create_subscription(
            PolicyDecision,
            "/astra/goals/decision",
            self.on_policy,
            decision_qos,
            callback_group=callbacks,
        )
        self.create_subscription(
            SafetyState,
            "/astra/safety/state",
            self.on_safety,
            decision_qos,
            callback_group=callbacks,
        )
        self.create_subscription(
            EntityState,
            "/astra/world/entities",
            self.on_entity,
            8,
            callback_group=callbacks,
        )
        self.create_subscription(
            Odometry,
            "/astra/sensors/odom",
            self.on_odom,
            QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT),
            callback_group=callbacks,
        )
        self.action = ActionServer(
            self,
            SkillInvocation,
            "/astra/skills/invoke",
            execute_callback=self.execute,
            goal_callback=self.accept_goal,
            cancel_callback=self.accept_cancel,
            callback_group=callbacks,
        )
        self.publish_catalog()

    def publish_catalog(self):
        for contract in SKILLS.values():
            descriptor = SkillDescriptor()
            descriptor.schema_version = "astra.skill-descriptor.v1"
            descriptor.name = contract.name
            descriptor.frame_id = "map"
            descriptor.clock_domain = "sim"
            descriptor.valid_at = self.get_clock().now().to_msg()
            descriptor.timeout_seconds = float(contract.timeout_seconds)
            descriptor.requires_human_approval = contract.requires_human_approval
            descriptor.preconditions = list(contract.preconditions)
            descriptor.postconditions = list(contract.postconditions)
            self.catalog.publish(descriptor)

    def on_policy(self, decision):
        with self.lock:
            self.policy = decision
            self.policy_wall = time.monotonic()

    def on_safety(self, safety):
        with self.lock:
            self.safety = safety
            self.safety_wall = time.monotonic()

    def on_entity(self, entity):
        with self.lock:
            self.entities[entity.entity_id] = (entity, time.monotonic())

    def on_odom(self, odom):
        stamp = odom.header.stamp.sec * 10**9 + odom.header.stamp.nanosec
        age = (self.get_clock().now().nanoseconds - stamp) / 10**9
        if (
            odom.header.frame_id != "odom"
            or odom.child_frame_id != "base_link"
            or not -0.05 <= age <= 0.25
            or not math.isfinite(odom.pose.pose.position.x)
            or not math.isfinite(odom.pose.pose.position.y)
        ):
            if not self.odom_diagnostic_logged:
                self.get_logger().warning(
                    f"odometry rejected frame={odom.header.frame_id} child={odom.child_frame_id} age={age:.3f}"
                )
                self.odom_diagnostic_logged = True
            return
        with self.lock:
            self.odom = odom
            self.odom_wall = time.monotonic()

    def accept_goal(self, request):
        contract = SKILLS.get(request.skill_name)
        if (
            request.schema_version != "astra.skill-invocation.v1"
            or contract is None
            or not MISSION_ID.fullmatch(request.mission_id)
            or not TARGET_ID.fullmatch(request.target_id)
            or request.frame_id != "map"
            or request.clock_domain != "sim"
            or not math.isfinite(request.timeout_seconds)
            or not 0 < request.timeout_seconds <= contract.timeout_seconds
        ):
            return GoalResponse.REJECT
        age = (
            self.get_clock().now().nanoseconds
            - (request.requested_at.sec * 10**9 + request.requested_at.nanosec)
        ) / 10**9
        if not -0.05 <= age <= 1.0:
            return GoalResponse.REJECT
        key = (request.mission_id, request.skill_name, request.target_id)
        with self.lock:
            return GoalResponse.REJECT if key in self.running else GoalResponse.ACCEPT

    def accept_cancel(self, _goal_handle):
        return CancelResponse.ACCEPT

    def policy_state(self, mission_id):
        with self.lock:
            decision, received = self.policy, self.policy_wall
        if decision is None or decision.mission_id != mission_id:
            return "PENDING"
        if not decision.allowed:
            return "DENIED"
        age = (
            self.get_clock().now().nanoseconds
            - (decision.decided_at.sec * 10**9 + decision.decided_at.nanosec)
        ) / 10**9
        if (
            decision.schema_version == "astra.policy-decision.v1"
            and decision.result_code == "OK"
            and decision.clock_domain == "sim"
            and decision.frame_id == "map"
            and -0.05 <= age <= 1.0
            and time.monotonic() - received <= 1.0
        ):
            return "ALLOWED"
        return "PENDING"

    def safety_state(self):
        with self.lock:
            state, received = self.safety, self.safety_wall
        if state is None or time.monotonic() - received > 0.75:
            return "STALE"
        if state.schema_version != "astra.safety-state.v1":
            return "INVALID"
        if state.mode in STOP_MODES or state.estop_latched:
            return "STOPPED"
        if state.mode in {"SAFE_IDLE", "ACTIVE"} and state.sensor_age_seconds <= 0.75:
            return "READY"
        return "PENDING"

    def fresh_entity(self, entity_id):
        with self.lock:
            entry = self.entities.get(entity_id)
        if entry is None:
            return None
        entity, received = entry
        if time.monotonic() - received > 0.75:
            return None
        valid_until = entity.valid_until.sec * 10**9 + entity.valid_until.nanosec
        if valid_until < self.get_clock().now().nanoseconds:
            return None
        sources = {
            "object-00": ("camera_optical_frame", "/astra/sensors/rgbd/image"),
            "obstacle/front": (
                "astra/base_footprint/lidar_2d",
                "/astra/sensors/scan",
            ),
        }
        if (
            entity.schema_version != "astra.entity-state.v1"
            or entity.clock_domain != "sim"
            or (entity.frame_id, entity.provenance) != sources.get(entity_id)
            or not 0.7 <= entity.confidence <= 1.0
        ):
            return None
        return entity

    def publish_feedback(self, goal_handle, code, progress, reason):
        request = goal_handle.request
        action_feedback = SkillInvocation.Feedback()
        action_feedback.skill_name = request.skill_name
        action_feedback.progress_ratio = progress
        action_feedback.result_code = code
        goal_handle.publish_feedback(action_feedback)
        stream = SkillFeedback()
        stream.schema_version = "astra.skill-feedback.v1"
        stream.mission_id = request.mission_id
        stream.skill_name = request.skill_name
        stream.frame_id = request.frame_id
        stream.clock_domain = "sim"
        stream.observed_at = self.get_clock().now().to_msg()
        stream.progress_ratio = progress
        stream.result_code = code
        stream.reason = reason
        self.feedback_pub.publish(stream)

    def send_intent(self, mission_id, linear=0.0, angular=0.0):
        intent = ControlIntent()
        intent.schema_version = "astra.control-intent.v1"
        intent.mission_id = mission_id
        intent.frame_id = "base_link"
        intent.clock_domain = "sim"
        intent.issued_at = self.get_clock().now().to_msg()
        intent.ttl_seconds = 0.2
        intent.linear_meters_per_second = float(linear)
        intent.angular_radians_per_second = float(angular)
        self.intent.publish(intent)

    def zero_intent(self, mission_id):
        self.send_intent(mission_id)
        self.disarm.publish(Bool(data=False))

    def align_base(self, goal_handle, deadline):
        mission_id = goal_handle.request.mission_id
        target_id = goal_handle.request.target_id
        centered = 0
        iterations = 0
        while time.monotonic() < deadline:
            if goal_handle.is_cancel_requested:
                return "CANCELED", "operator_cancel"
            safety = self.safety_state()
            if safety == "STOPPED":
                with self.lock:
                    reason = (
                        self.safety.reason if self.safety is not None else "unknown"
                    )
                return "SAFETY_STOP", reason
            if safety != "READY":
                return "SAFETY_NOT_READY", "safety_or_sensor_heartbeat_missing"
            with self.lock:
                active = self.safety is not None and self.safety.mode == "ACTIVE"
                odom_fresh = (
                    self.odom is not None and time.monotonic() - self.odom_wall <= 0.5
                )
            if not active or not odom_fresh:
                time.sleep(0.05)
                continue
            if self.policy_state(mission_id) != "ALLOWED":
                return "POLICY_DENIED", "goal_policy_expired_or_revoked"
            entity = self.fresh_entity(target_id)
            if entity is None:
                self.get_logger().warning("alignment lost fresh RGB-D target")
                return "STALE_TARGET", "rgbd_target_fact_expired"
            horizontal = entity.pose.pose.position.x
            depth = entity.pose.pose.position.z
            if (
                not math.isfinite(horizontal)
                or not math.isfinite(depth)
                or depth <= 0.1
            ):
                return "INVALID_TARGET", "nonfinite_or_invalid_rgbd_pose"
            error = math.atan2(horizontal, depth)
            iterations += 1
            if iterations % 10 == 1:
                self.get_logger().info(
                    f"alignment bearing={error:.3f} horizontal={horizontal:.3f} depth={depth:.3f}"
                )
            if abs(error) <= 0.06:
                centered += 1
                self.send_intent(mission_id)
                if centered >= 3:
                    self.zero_intent(mission_id)
                    return "OK", "rgbd_target_centered_with_odometry_and_safety"
            else:
                centered = 0
                angular = max(-0.3, min(0.3, 1.2 * error))
                self.send_intent(mission_id, angular=angular)
            time.sleep(0.05)
        return "TIMEOUT", "alignment_deadline_exceeded"

    def execute(self, goal_handle):
        request = goal_handle.request
        key = (request.mission_id, request.skill_name, request.target_id)
        with self.lock:
            cached = (
                self.completed.get(key) if request.skill_name in CACHEABLE else None
            )
            if cached is None:
                self.running.add(key)
        try:
            if cached is not None:
                code, reason = cached
            else:
                self.publish_feedback(goal_handle, "RUNNING", 0.0, "skill_started")
                code, reason = self.run_skill(goal_handle)
            result = SkillInvocation.Result()
            result.completed = code == "OK"
            result.result_code = code
            result.reason = reason
            self.publish_feedback(
                goal_handle, code, 1.0 if code == "OK" else 0.0, reason
            )
            if code == "CANCELED":
                self.zero_intent(request.mission_id)
                goal_handle.canceled()
            elif code == "OK":
                if request.skill_name in CACHEABLE:
                    with self.lock:
                        self.completed[key] = (code, reason)
                goal_handle.succeed()
            else:
                self.zero_intent(request.mission_id)
                goal_handle.abort()
            return result
        finally:
            with self.lock:
                self.running.discard(key)

    def run_skill(self, goal_handle):
        request = goal_handle.request
        if request.skill_name == "safe_stop":
            self.zero_intent(request.mission_id)
            return "OK", "zero_intent_and_disarm_requested"
        deadline = time.monotonic() + request.timeout_seconds
        if request.skill_name == "align_base":
            return self.align_base(goal_handle, deadline)
        while time.monotonic() < deadline:
            if goal_handle.is_cancel_requested:
                return "CANCELED", "operator_cancel"
            if self.safety_state() == "STOPPED":
                return "SAFETY_STOP", "safety_supervisor_not_ready"
            policy = self.policy_state(request.mission_id)
            if policy == "DENIED":
                return "POLICY_DENIED", "goal_policy_revoked"
            if policy != "ALLOWED":
                time.sleep(0.05)
                continue
            if request.skill_name in {
                "observe_area",
                "locate_entity",
                "inspect_entity",
            }:
                if self.fresh_entity(request.target_id) is not None:
                    if request.skill_name == "inspect_entity":
                        with self.lock:
                            self.inspected.add((request.mission_id, request.target_id))
                    return "OK", "fresh_rgbd_target_fact"
            elif request.skill_name == "wait_for_clearance":
                obstacle = self.fresh_entity("obstacle/front")
                if obstacle is not None and obstacle.pose.pose.position.x >= 0.8:
                    return "OK", "lidar_front_clear"
            elif request.skill_name == "speak_report":
                with self.lock:
                    inspected = (
                        request.mission_id,
                        request.target_id,
                    ) in self.inspected
                if inspected:
                    report = String()
                    report.data = json.dumps(
                        {
                            "mission_id": request.mission_id,
                            "target_id": request.target_id,
                            "result_code": "INSPECTED",
                        },
                        sort_keys=True,
                    )
                    self.speech.publish(report)
                    return "OK", "simulated_speaker_report_published"
            elif request.skill_name in {
                "navigate_to",
                "align_base",
                "point_at",
                "return_home",
            }:
                return "CONTROL_ADAPTER_UNAVAILABLE", "motion_adapter_not_commissioned"
            time.sleep(0.05)
        return "TIMEOUT", "skill_deadline_exceeded"


def main():
    rclpy.init()
    node = SkillServer()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
