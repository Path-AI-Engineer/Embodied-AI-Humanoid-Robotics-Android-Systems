#!/usr/bin/env python3
"""Independent simulation-only authorization boundary for Astra arm pointing."""

import math
import re
import threading
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import EntityState, PolicyDecision, SafetyState
from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool
from trajectory_msgs.msg import JointTrajectoryPoint


MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


class ArmControlGateway(Node):
    def __init__(self):
        super().__init__("arm_control_gateway")
        self.lock = threading.RLock()
        self.running = False
        self.policy = None
        self.policy_wall = 0.0
        self.safety = None
        self.safety_wall = 0.0
        self.target = None
        self.target_wall = 0.0
        callbacks = ReentrantCallbackGroup()
        durable = QoSProfile(
            depth=4,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            PolicyDecision,
            "/astra/goals/decision",
            self.on_policy,
            durable,
            callback_group=callbacks,
        )
        self.create_subscription(
            SafetyState,
            "/astra/safety/state",
            self.on_safety,
            durable,
            callback_group=callbacks,
        )
        self.create_subscription(
            EntityState,
            "/astra/world/entities",
            self.on_target,
            8,
            callback_group=callbacks,
        )
        self.disarm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.controller = ActionClient(
            self,
            FollowJointTrajectory,
            "/arm_controller/follow_joint_trajectory",
            callback_group=callbacks,
        )
        self.action = ActionServer(
            self,
            SkillInvocation,
            "/astra/control/point_at",
            execute_callback=self.execute,
            goal_callback=self.accept_goal,
            cancel_callback=lambda _goal: CancelResponse.ACCEPT,
            callback_group=callbacks,
        )

    def on_policy(self, message):
        with self.lock:
            self.policy = message
            self.policy_wall = time.monotonic()

    def on_safety(self, message):
        with self.lock:
            self.safety = message
            self.safety_wall = time.monotonic()

    def on_target(self, message):
        if message.entity_id == "object-00":
            with self.lock:
                self.target = message
                self.target_wall = time.monotonic()

    def accept_goal(self, request):
        stamp = request.requested_at.sec * 10**9 + request.requested_at.nanosec
        age = (self.get_clock().now().nanoseconds - stamp) / 10**9
        if (
            request.schema_version != "astra.skill-invocation.v1"
            or request.skill_name != "point_at"
            or request.target_id != "object-00"
            or not MISSION_ID.fullmatch(request.mission_id)
            or request.frame_id != "map"
            or request.clock_domain != "sim"
            or not math.isfinite(request.timeout_seconds)
            or not 0 < request.timeout_seconds <= 10
            or not -0.05 <= age <= 1.0
        ):
            return GoalResponse.REJECT
        if self.authorized(request.mission_id)[1] != "OK":
            return GoalResponse.REJECT
        with self.lock:
            if self.running:
                return GoalResponse.REJECT
            self.running = True
        return GoalResponse.ACCEPT

    def authorized(self, mission_id):
        with self.lock:
            policy = self.policy
            policy_wall = self.policy_wall
            safety = self.safety
            safety_wall = self.safety_wall
            target = self.target
            target_wall = self.target_wall
        wall = time.monotonic()
        if (
            policy is None
            or policy.mission_id != mission_id
            or not policy.allowed
            or policy.result_code != "OK"
            or policy.schema_version != "astra.policy-decision.v1"
            or policy.frame_id != "map"
            or policy.clock_domain != "sim"
            or wall - policy_wall > 1.0
        ):
            return None, "POLICY_DENIED"
        policy_stamp = policy.decided_at.sec * 10**9 + policy.decided_at.nanosec
        policy_age = (self.get_clock().now().nanoseconds - policy_stamp) / 10**9
        if not -0.05 <= policy_age <= 1.0:
            return None, "POLICY_DENIED"
        if (
            safety is None
            or safety.schema_version != "astra.safety-state.v1"
            or safety.mode != "ACTIVE"
            or safety.estop_latched
            or safety.sensor_age_seconds > 0.75
            or wall - safety_wall > 0.75
        ):
            return None, "SAFETY_STOP"
        if (
            target is None
            or target.schema_version != "astra.entity-state.v1"
            or target.frame_id != "camera_optical_frame"
            or target.clock_domain != "sim"
            or target.provenance != "/astra/sensors/rgbd/image"
            or not 0.7 <= target.confidence <= 1.0
            or wall - target_wall > 0.75
        ):
            return None, "STALE_TARGET"
        valid_until = target.valid_until.sec * 10**9 + target.valid_until.nanosec
        if valid_until < self.get_clock().now().nanoseconds:
            return None, "STALE_TARGET"
        x, z = target.pose.pose.position.x, target.pose.pose.position.z
        if not math.isfinite(x) or not math.isfinite(z) or z <= 0.1:
            return None, "INVALID_TARGET"
        return max(-0.4, min(0.4, math.atan2(x, z))), "OK"

    def execute(self, goal_handle):
        request = goal_handle.request
        deadline = time.monotonic() + request.timeout_seconds
        controller_goal = None
        accepted = None
        result_future = None
        code = "TIMEOUT"
        reason = "arm_gateway_deadline_exceeded"
        try:
            bearing, code = self.authorized(request.mission_id)
            if code != "OK":
                reason = "arm_gateway_precondition_failed"
            elif not self.controller.wait_for_server(timeout_sec=1.0):
                code, reason = "CONTROL_ADAPTER_UNAVAILABLE", "arm_controller_missing"
            else:
                command = FollowJointTrajectory.Goal()
                command.trajectory.joint_names = [
                    f"arm_joint_{joint}" for joint in range(1, 7)
                ]
                point = JointTrajectoryPoint()
                point.positions = [bearing, -0.25, 0.45, 0.0, 0.0, 0.0]
                point.time_from_start = Duration(sec=2)
                command.trajectory.points = [point]
                accepted = self.controller.send_goal_async(command)
                while time.monotonic() < deadline:
                    if goal_handle.is_cancel_requested:
                        code, reason = "CANCELED", "operator_cancel"
                        break
                    _, authorization = self.authorized(request.mission_id)
                    if authorization != "OK":
                        code, reason = authorization, "arm_gateway_authorization_lost"
                        break
                    if controller_goal is None and accepted.done():
                        controller_goal = accepted.result()
                        if not controller_goal.accepted:
                            code, reason = "CONTROL_REJECTED", "arm_trajectory_rejected"
                            break
                        result_future = controller_goal.get_result_async()
                    if result_future is not None and result_future.done():
                        outcome = result_future.result().result
                        code = "OK" if outcome.error_code == 0 else "CONTROL_FAILED"
                        reason = (
                            "bounded_arm_trajectory_completed"
                            if code == "OK"
                            else f"arm_result_{outcome.error_code}"
                        )
                        break
                    time.sleep(0.05)
                if code != "OK":
                    if (
                        controller_goal is None
                        and accepted is not None
                        and accepted.done()
                    ):
                        controller_goal = accepted.result()
                    if controller_goal is not None and controller_goal.accepted:
                        controller_goal.cancel_goal_async()
            self.disarm.publish(Bool(data=False))
            if code == "OK":
                settled_by = time.monotonic() + 2.0
                while time.monotonic() < settled_by:
                    with self.lock:
                        settled = (
                            self.safety is not None and self.safety.mode == "SAFE_IDLE"
                        )
                    if settled:
                        break
                    time.sleep(0.05)
                else:
                    with self.lock:
                        mode = self.safety.mode if self.safety is not None else "NONE"
                        state_reason = (
                            self.safety.reason if self.safety is not None else "none"
                        )
                    code, reason = (
                        "SAFETY_STOP",
                        f"arm_disarm_unconfirmed:{mode}:{state_reason}",
                    )
            if code != "OK":
                self.get_logger().warning(
                    f"point_at mission={request.mission_id} code={code} reason={reason}"
                )
            result = SkillInvocation.Result()
            result.completed = code == "OK"
            result.result_code = code
            result.reason = reason
            if code == "OK":
                goal_handle.succeed()
            elif code == "CANCELED":
                goal_handle.canceled()
            else:
                goal_handle.abort()
            return result
        finally:
            with self.lock:
                self.running = False


def main():
    rclpy.init()
    node = ArmControlGateway()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
