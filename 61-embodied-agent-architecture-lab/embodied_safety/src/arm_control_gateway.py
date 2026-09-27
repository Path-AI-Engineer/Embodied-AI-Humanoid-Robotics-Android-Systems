#!/usr/bin/env python3
"""Independent simulation-only authorization boundary for Astra arm pointing."""

import math
import re
import threading
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import EntityState, PolicyDecision, SafetyState
from control_msgs.action import FollowJointTrajectory
from control_msgs.msg import JointTrajectoryControllerState
from moveit_msgs.msg import Constraints, JointConstraint
from moveit_msgs.srv import GetMotionPlan
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool


MISSION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
ARM_JOINTS = [f"arm_joint_{joint}" for joint in range(1, 7)]


class ArmControlGateway(Node):
    def __init__(self):
        super().__init__("arm_control_gateway")
        self.lock = threading.RLock()
        self.running = False
        self.policies = {}
        self.safety = None
        self.safety_wall = 0.0
        self.target = None
        self.target_wall = 0.0
        self.joints = None
        self.joints_wall = 0.0
        self.joint_messages = 0
        self.controller_state_messages = 0
        self.joint_names_seen = ()
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
            "/astra/world/object_target",
            self.on_target,
            8,
            callback_group=callbacks,
        )
        self.disarm = self.create_publisher(Bool, "/astra/safety/arm", 1)
        self.create_subscription(
            JointState,
            "/joint_states",
            self.on_joints,
            QoSProfile(depth=4, reliability=ReliabilityPolicy.BEST_EFFORT),
            callback_group=callbacks,
        )
        self.create_subscription(
            JointTrajectoryControllerState,
            "/arm_controller/controller_state",
            self.on_controller_state,
            QoSProfile(depth=4, reliability=ReliabilityPolicy.RELIABLE),
            callback_group=callbacks,
        )
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
            self.policies[message.mission_id] = (message, time.monotonic())
            if len(self.policies) > 64:
                oldest = min(self.policies, key=lambda key: self.policies[key][1])
                del self.policies[oldest]

    def on_safety(self, message):
        with self.lock:
            self.safety = message
            self.safety_wall = time.monotonic()

    def on_target(self, message):
        if message.entity_id == "object-00":
            with self.lock:
                self.target = message
                self.target_wall = time.monotonic()

    def log_stale_target(self):
        with self.lock:
            target = self.target
            target_wall = self.target_wall
        wall_age = round(time.monotonic() - target_wall, 3) if target_wall else None
        sim_remaining = None
        if target is not None:
            valid_ns = target.valid_until.sec * 10**9 + target.valid_until.nanosec
            sim_remaining = round(
                (valid_ns - self.get_clock().now().nanoseconds) / 1e9, 3
            )
        self.get_logger().warning(
            f"object target stale: wall_age={wall_age} "
            f"sim_remaining={sim_remaining} "
            f"publishers={self.count_publishers('/astra/world/object_target')}"
        )

    def on_joints(self, message):
        by_name = dict(zip(message.name, message.position, strict=False))
        with self.lock:
            self.joint_messages += 1
            self.joint_names_seen = tuple(message.name)
        if all(name in by_name and math.isfinite(by_name[name]) for name in ARM_JOINTS):
            with self.lock:
                self.joints = [by_name[name] for name in ARM_JOINTS]
                self.joints_wall = time.monotonic()

    def on_controller_state(self, message):
        by_name = dict(
            zip(message.joint_names, message.feedback.positions, strict=False)
        )
        with self.lock:
            self.controller_state_messages += 1
        if all(name in by_name and math.isfinite(by_name[name]) for name in ARM_JOINTS):
            with self.lock:
                self.joints = [by_name[name] for name in ARM_JOINTS]
                self.joints_wall = time.monotonic()

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
        _, authorization = self.authorized(request.mission_id)
        if authorization != "OK":
            self.get_logger().warning(
                f"point_at goal rejected mission={request.mission_id} reason={authorization}"
            )
            return GoalResponse.REJECT
        with self.lock:
            if self.running:
                return GoalResponse.REJECT
            self.running = True
        return GoalResponse.ACCEPT

    def authorized(self, mission_id):
        with self.lock:
            policy, policy_wall = self.policies.get(mission_id, (None, 0.0))
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

    def plan(self, goal_handle, bearing, deadline):
        joint_deadline = min(deadline, time.monotonic() + 2.0)
        while True:
            with self.lock:
                joints = self.joints
                joints_wall = self.joints_wall
            if joints is not None and time.monotonic() - joints_wall <= 0.5:
                break
            if goal_handle.is_cancel_requested:
                return None, "CANCELED", "operator_cancel_waiting_for_joint_state"
            if self.authorized(goal_handle.request.mission_id)[1] != "OK":
                return None, "SAFETY_STOP", "authorization_lost_waiting_for_joint_state"
            if time.monotonic() >= joint_deadline:
                with self.lock:
                    messages = self.joint_messages
                    controller_messages = self.controller_state_messages
                    names = self.joint_names_seen
                age = round(time.monotonic() - joints_wall, 3) if joints_wall else None
                return (
                    None,
                    "STALE_JOINT_STATE",
                    f"arm_joint_state_unavailable:messages={messages}:"
                    f"controller_messages={controller_messages}:"
                    f"age={age}:publishers={self.count_publishers('/joint_states')}:"
                    f"names={names}",
                )
            time.sleep(0.02)
        target = [bearing, -0.25, 0.45, 0.0, 0.0, 0.0]
        request = GetMotionPlan.Request()
        motion = request.motion_plan_request
        motion.group_name = "arm"
        motion.pipeline_id = "ompl"
        motion.num_planning_attempts = 2
        motion.allowed_planning_time = 2.0
        motion.start_state.joint_state.name = ARM_JOINTS
        motion.start_state.joint_state.position = joints
        motion.start_state.is_diff = False
        constraints = Constraints()
        for name, position in zip(ARM_JOINTS, target, strict=True):
            joint = JointConstraint()
            joint.joint_name = name
            joint.position = position
            joint.tolerance_above = 0.02
            joint.tolerance_below = 0.02
            joint.weight = 1.0
            constraints.joint_constraints.append(joint)
        motion.goal_constraints = [constraints]
        # Give planning its own ROS node/participant. The standalone planning
        # probe can discover MoveIt even when the gateway participant sees the
        # service name but cannot match its client endpoint.
        planner_node = rclpy.create_node("astra_arm_planning_client")
        try:
            planner = planner_node.create_client(GetMotionPlan, "/plan_kinematic_path")
            while not planner.wait_for_service(timeout_sec=0.1):
                if goal_handle.is_cancel_requested:
                    return None, "CANCELED", "operator_cancel_waiting_for_moveit"
                authorization = self.authorized(goal_handle.request.mission_id)[1]
                if authorization != "OK":
                    if authorization == "STALE_TARGET":
                        self.log_stale_target()
                    return (
                        None,
                        authorization,
                        f"authorization_lost_waiting_for_moveit:{authorization}",
                    )
                if time.monotonic() >= deadline:
                    services = [
                        (name, types)
                        for name, types in planner_node.get_service_names_and_types()
                        if "plan_kinematic_path" in name
                    ]
                    self.get_logger().warning(
                        f"moveit service not discovered by planning node: {services}"
                    )
                    return (
                        None,
                        "PLANNER_UNAVAILABLE",
                        "moveit_planning_service_missing",
                    )
            future = planner.call_async(request)
            while not future.done() and time.monotonic() < deadline:
                rclpy.spin_once(planner_node, timeout_sec=0.02)
                if goal_handle.is_cancel_requested:
                    future.cancel()
                    return None, "CANCELED", "operator_cancel_during_planning"
                authorization = self.authorized(goal_handle.request.mission_id)[1]
                if authorization != "OK":
                    if authorization == "STALE_TARGET":
                        self.log_stale_target()
                    future.cancel()
                    return (
                        None,
                        authorization,
                        f"authorization_lost_during_planning:{authorization}",
                    )
            if not future.done():
                future.cancel()
                return None, "TIMEOUT", "moveit_planning_deadline_exceeded"
            try:
                response = future.result().motion_plan_response
            except Exception as exc:
                return (
                    None,
                    "PLANNER_FAILED",
                    f"moveit_service_error:{type(exc).__name__}",
                )
        finally:
            planner_node.destroy_node()
        trajectory = response.trajectory.joint_trajectory
        if response.error_code.val != 1 or trajectory.joint_names != ARM_JOINTS:
            return None, "PLANNER_FAILED", f"moveit_result_{response.error_code.val}"
        points = trajectory.points
        if len(points) < 2:
            return None, "PLANNER_FAILED", "moveit_trajectory_too_short"
        for point in points:
            if len(point.positions) != 6 or any(
                not math.isfinite(position) or abs(position) > 1.5
                for position in point.positions
            ):
                return None, "PLANNER_FAILED", "moveit_joint_limits_invalid"
        if any(
            abs(actual - expected) > 0.03
            for actual, expected in zip(points[-1].positions, target, strict=True)
        ):
            return None, "PLANNER_FAILED", "moveit_goal_not_reached"
        duration = (
            points[-1].time_from_start.sec + points[-1].time_from_start.nanosec / 1e9
        )
        if duration <= 0 or duration > max(0, deadline - time.monotonic()):
            return None, "PLANNER_FAILED", "moveit_trajectory_exceeds_deadline"
        trajectory.header.stamp = self.get_clock().now().to_msg()
        return trajectory, "OK", "moveit_plan_validated"

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
            else:
                trajectory, code, reason = self.plan(goal_handle, bearing, deadline)
            if code == "OK" and not self.controller.wait_for_server(timeout_sec=1.0):
                code, reason = "CONTROL_ADAPTER_UNAVAILABLE", "arm_controller_missing"
            if code == "OK":
                command = FollowJointTrajectory.Goal()
                command.trajectory = trajectory
                accepted = self.controller.send_goal_async(command)
                while time.monotonic() < deadline:
                    if goal_handle.is_cancel_requested:
                        code, reason = "CANCELED", "operator_cancel"
                        break
                    _, authorization = self.authorized(request.mission_id)
                    if authorization != "OK":
                        with self.lock:
                            safety_reason = (
                                self.safety.reason
                                if self.safety is not None
                                else "none"
                            )
                        code, reason = (
                            authorization,
                            f"arm_gateway_authorization_lost:{safety_reason}",
                        )
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
                    if (
                        controller_goal is not None
                        and controller_goal.accepted
                        and (result_future is None or not result_future.done())
                    ):
                        cancellation = controller_goal.cancel_goal_async()
                        cancel_deadline = time.monotonic() + 1.0
                        while (
                            not cancellation.done()
                            and time.monotonic() < cancel_deadline
                        ):
                            time.sleep(0.02)
                        if not cancellation.done():
                            code, reason = (
                                "CONTROL_CANCEL_UNCONFIRMED",
                                "arm_controller_cancel_timeout",
                            )
                        else:
                            try:
                                canceled_goals = cancellation.result().goals_canceling
                            except Exception:
                                canceled_goals = []
                            if not canceled_goals:
                                code, reason = (
                                    "CONTROL_CANCEL_UNCONFIRMED",
                                    "arm_controller_cancel_rejected",
                                )
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
