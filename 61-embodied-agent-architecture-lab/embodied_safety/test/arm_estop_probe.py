"""Inject E-stop during a real arm trajectory and measure simulated settling."""

import json
import time

import rclpy
from astra_interfaces.action import SkillInvocation
from astra_interfaces.msg import ControlIntent, GoalRequest
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool

from ros_gate_probe import Probe, arm_with_fresh_policy


MISSION = "arm-estop-probe"


class ArmStopProbe(Probe):
    def __init__(self):
        super().__init__()
        self.samples = []
        self.create_subscription(
            JointState,
            "/joint_states",
            self.on_joints,
            QoSProfile(depth=8, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        self.zero_intent = ControlIntent()
        self.zero_intent.schema_version = "astra.control-intent.v1"
        self.zero_intent.mission_id = MISSION
        self.zero_intent.frame_id = "base_link"
        self.zero_intent.clock_domain = "sim"
        self.zero_intent.ttl_seconds = 0.2
        self.last_pulse = 0.0

    def on_joints(self, message):
        speeds = [
            abs(message.velocity[index])
            for index, name in enumerate(message.name)
            if name.startswith("arm_joint_") and index < len(message.velocity)
        ]
        if len(speeds) == 6:
            self.samples.append((time.monotonic(), max(speeds)))

    def pulse(self, goal):
        now = time.monotonic()
        if now - self.last_pulse < 0.1:
            return
        goal.requested_at = self.get_clock().now().to_msg()
        self.goals.publish(goal)
        self.zero_intent.issued_at = goal.requested_at
        self.intent.publish(self.zero_intent)
        self.last_pulse = now


def main():
    rclpy.init()
    node = ArmStopProbe()
    try:
        node.until(lambda: any(e.entity_id == "object-00" for e in node.entities), 45)
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE", 20)
        node.until(lambda: node.arm_action.server_is_ready())
        goal = GoalRequest()
        goal.schema_version = "astra.goal-request.v1"
        goal.mission_id = MISSION
        goal.target_id = "object-00"
        goal.station_id = "inspection-station"
        goal.requested_by = "local-operator"
        goal.frame_id = "map"
        goal.clock_domain = "sim"
        goal.ttl_seconds = 0.8
        arm_with_fresh_policy(node, goal)

        request = SkillInvocation.Goal()
        request.schema_version = "astra.skill-invocation.v1"
        request.mission_id = MISSION
        request.skill_name = "point_at"
        request.target_id = "object-00"
        request.frame_id = "map"
        request.clock_domain = "sim"
        request.requested_at = node.get_clock().now().to_msg()
        request.timeout_seconds = 5.0
        sent = node.arm_action.send_goal_async(request)
        start = time.monotonic()
        while not sent.done() and time.monotonic() - start < 3:
            node.pulse(goal)
            rclpy.spin_once(node, timeout_sec=0.03)
        assert sent.done() and sent.result().accepted, "arm goal not accepted"
        handle = sent.result()
        result = handle.get_result_async()

        moving_by = time.monotonic() + 2
        while time.monotonic() < moving_by:
            node.pulse(goal)
            rclpy.spin_once(node, timeout_sec=0.02)
            if node.samples and node.samples[-1][1] > 0.08:
                break
        else:
            raise AssertionError("arm never moved before E-stop injection")

        node.estop.publish(Bool(data=True))
        node.until(
            lambda: node.states
            and node.states[-1].mode == "EMERGENCY_STOP"
            and node.states[-1].estop_latched,
            2,
        )
        observed_stop = time.monotonic()
        node.until(lambda: result.done(), 3)
        assert result.result().result.result_code != "OK", (
            "arm reported success after E-stop"
        )

        settle_by = observed_stop + 1.0
        settled = None
        while time.monotonic() < settle_by:
            rclpy.spin_once(node, timeout_sec=0.02)
            if node.samples and node.samples[-1][1] <= 0.05:
                settled = time.monotonic()
                break
        assert settled is not None, "arm velocity did not settle within one wall second"
        hold_until = time.monotonic() + 0.4
        while time.monotonic() < hold_until:
            rclpy.spin_once(node, timeout_sec=0.02)
        later = [speed for stamp, speed in node.samples if stamp >= settled]
        assert later and max(later) <= 0.08, f"arm resumed while latched: {max(later)}"
        node.recover.publish(Bool(data=True))
        node.until(lambda: node.states and node.states[-1].mode == "SAFE_IDLE", 3)
        print(
            json.dumps(
                {
                    "arm_estop_result": result.result().result.result_code,
                    "settle_wall_seconds": round(settled - observed_stop, 3),
                    "latched_motion_max_rad_per_second": round(max(later), 4),
                    "explicit_recovery": "SAFE_IDLE",
                },
                sort_keys=True,
            )
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
