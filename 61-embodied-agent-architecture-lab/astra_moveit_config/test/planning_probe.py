"""Demand a collision-checked, planning-only six-joint MoveIt trajectory."""

import json
import time

import rclpy
from moveit_msgs.msg import Constraints, JointConstraint
from moveit_msgs.srv import GetMotionPlan
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState


JOINTS = [f"arm_joint_{index}" for index in range(1, 7)]
GOAL = [0.0, -0.25, 0.45, 0.0, 0.0, 0.0]


class PlanningProbe(Node):
    def __init__(self):
        super().__init__(
            "moveit_planning_probe",
            parameter_overrides=[Parameter("use_sim_time", value=True)],
        )
        self.joints = None
        self.create_subscription(JointState, "/joint_states", self.on_joints, 8)
        self.client = self.create_client(GetMotionPlan, "/plan_kinematic_path")

    def on_joints(self, message):
        by_name = dict(zip(message.name, message.position, strict=False))
        if all(name in by_name for name in JOINTS):
            self.joints = [by_name[name] for name in JOINTS]


def main():
    rclpy.init()
    node = PlanningProbe()
    try:
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.joints is not None and node.client.service_is_ready():
                break
        else:
            raise AssertionError("joint state or MoveIt planning service unavailable")

        request = GetMotionPlan.Request()
        plan = request.motion_plan_request
        plan.group_name = "arm"
        plan.num_planning_attempts = 3
        plan.allowed_planning_time = 5.0
        plan.start_state.joint_state.name = JOINTS
        plan.start_state.joint_state.position = node.joints
        plan.start_state.is_diff = False
        goal = Constraints()
        for name, position in zip(JOINTS, GOAL, strict=True):
            joint = JointConstraint()
            joint.joint_name = name
            joint.position = position
            joint.tolerance_above = 0.02
            joint.tolerance_below = 0.02
            joint.weight = 1.0
            goal.joint_constraints.append(joint)
        plan.goal_constraints = [goal]
        future = node.client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=12)
        if not future.done():
            raise AssertionError("MoveIt planning request timed out")
        result = future.result().motion_plan_response
        points = result.trajectory.joint_trajectory.points
        if result.error_code.val != 1 or not points:
            raise AssertionError(
                f"MoveIt failed to plan: code={result.error_code.val}, "
                f"points={len(points)}"
            )
        if result.trajectory.joint_trajectory.joint_names != JOINTS:
            raise AssertionError("MoveIt returned a different arm joint set")
        print(
            json.dumps(
                {
                    "status": "planned_not_executed",
                    "planning_group": "arm",
                    "joint_count": len(JOINTS),
                    "trajectory_points": len(points),
                },
                sort_keys=True,
            )
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
