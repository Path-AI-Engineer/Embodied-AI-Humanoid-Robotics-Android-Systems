"""Boundary matrix for the portable supervisor's fail-closed decisions."""

from __future__ import annotations

import math
import unittest
from dataclasses import replace

from embodied.contracts import ClockDomain, MotorCommand, ResultCode, SafetyMode, Stamp
from embodied.safety import SafetySignals, SafetySupervisor


NOW = Stamp(1.0, ClockDomain.SIM)
COMMAND = MotorCommand(0.0, 0.0, 0.0, NOW, Stamp(1.1, ClockDomain.SIM))
TELEMETRY_FAULTS = (
    ("contact", {"contact": True}),
    ("human_near", {"human_distance_m": 0.799}),
    ("heartbeat_stale", {"heartbeat_age_s": 0.501}),
    ("sensor_stale", {"sensor_age_s": 0.251}),
    ("transform_stale", {"transform_age_s": 0.201}),
    ("localization_low", {"localization_confidence": 0.699}),
    ("queue_overload", {"queue_depth": 17}),
    ("heartbeat_negative", {"heartbeat_age_s": -0.001}),
    ("sensor_negative", {"sensor_age_s": -0.001}),
    ("transform_negative", {"transform_age_s": -0.001}),
    ("human_negative", {"human_distance_m": -0.001}),
    ("localization_negative", {"localization_confidence": -0.001}),
    ("queue_negative", {"queue_depth": -1}),
    ("heartbeat_nan", {"heartbeat_age_s": math.nan}),
    ("sensor_nan", {"sensor_age_s": math.nan}),
    ("transform_nan", {"transform_age_s": math.nan}),
    ("human_nan", {"human_distance_m": math.nan}),
    ("localization_nan", {"localization_confidence": math.nan}),
)
MOTION_BOUNDS = (
    ("linear_mps", 0.35),
    ("angular_radps", 0.8),
    ("arm_velocity_radps", 0.5),
)


class SafetyBoundaryMatrixTests(unittest.TestCase):
    def test_telemetry_faults_reject_at_startup_and_during_motion(self) -> None:
        # 18 distinct faults x 2 lifecycle states = 36 safety cases.
        for name, changes in TELEMETRY_FAULTS:
            with self.subTest(fault=name, phase="self_check"):
                supervisor = SafetySupervisor()
                denied = supervisor.self_check(replace(SafetySignals(), **changes), NOW)
                self.assertFalse(denied.allowed)
                self.assertEqual(supervisor.mode, SafetyMode.PROTECTIVE_STOP)
                self.assertFalse(supervisor.activate().allowed)
            with self.subTest(fault=name, phase="active"):
                supervisor = SafetySupervisor()
                self.assertTrue(supervisor.self_check(SafetySignals(), NOW).allowed)
                self.assertTrue(supervisor.activate().allowed)
                denied = supervisor.authorize(
                    COMMAND, replace(SafetySignals(), **changes), NOW
                )
                self.assertEqual(denied.code, ResultCode.SAFETY_STOP)
                self.assertEqual(supervisor.mode, SafetyMode.PROTECTIVE_STOP)

    def test_each_signed_motion_limit_accepts_boundary_and_stops_above_it(self) -> None:
        # 3 axes x 2 directions x 2 boundary positions = 12 motion cases.
        for field_name, bound in MOTION_BOUNDS:
            for sign in (-1, 1):
                for excess in (0.0, 0.001):
                    with self.subTest(axis=field_name, sign=sign, excess=excess):
                        supervisor = SafetySupervisor()
                        self.assertTrue(
                            supervisor.self_check(SafetySignals(), NOW).allowed
                        )
                        self.assertTrue(supervisor.activate().allowed)
                        command = replace(
                            COMMAND, **{field_name: sign * (bound + excess)}
                        )
                        decision = supervisor.authorize(command, SafetySignals(), NOW)
                        if excess == 0.0:
                            self.assertEqual(decision.code, ResultCode.OK)
                            self.assertEqual(supervisor.mode, SafetyMode.ACTIVE)
                        else:
                            self.assertEqual(decision.code, ResultCode.SAFETY_STOP)
                            self.assertEqual(
                                supervisor.mode, SafetyMode.PROTECTIVE_STOP
                            )


if __name__ == "__main__":
    unittest.main()
