"""Pre-registered portable contract matrices; ROS graph gates remain separate."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from embodied.contracts import (
    ClockDomain,
    FRAME_IDS,
    GoalRequest,
    Observation,
    ResultCode,
    Stamp,
)
from embodied.evidence import build_record, replay_equivalent, verify_record
from embodied.executive import run_mission, scenario_from_dict
from embodied.runtime import GoalGateway
from embodied.simulation import Scenario


ROOT = Path(__file__).resolve().parents[1]
FAULTS = (
    "stale_percept",
    "frame_mismatch",
    "clock_mismatch",
    "low_confidence",
    "human_near",
    "bumper",
    "heartbeat_loss",
    "stale_tf",
    "localization_loss",
    "queue_overload",
    "estop",
)


class AcceptanceMatrixTests(unittest.TestCase):
    def test_96_fault_and_policy_missions_fail_closed(self) -> None:
        cases = 0
        for seed in range(8):
            base = Scenario(
                f"matrix-{seed}",
                8100 + seed,
                f"object-{seed:02d}",
                "inspection-station",
                1.0,
                0.5,
            )
            for fault in FAULTS:
                with self.subTest(seed=seed, fault=fault):
                    result = run_mission(replace(base, fault=fault))
                    self.assertEqual(result.outcome, "STOPPED")
                    self.assertEqual(result.score["unsafe_motor_commands"], 0)
                    self.assertEqual(result.events[-1]["kind"], "terminal")
                    cases += 1
            with self.subTest(seed=seed, fault="restricted_without_approval"):
                result = run_mission(replace(base, restricted_zone=True))
                self.assertEqual(result.outcome, "DENIED")
                self.assertEqual(result.score["motor_commands"], 0)
                cases += 1
        self.assertEqual(cases, 96)

    def test_64_frame_clock_and_freshness_contract_cases(self) -> None:
        cases = 0
        for frame in sorted(FRAME_IDS):
            observation = Observation(
                "rgbd",
                "object-00",
                frame,
                Stamp(1.0, ClockDomain.SIM),
                0.25,
                0.95,
                0.01,
                1.0,
                2.0,
            )
            variations = (
                (observation, Stamp(1.0, ClockDomain.SIM), ResultCode.OK),
                (observation, Stamp(1.25, ClockDomain.SIM), ResultCode.OK),
                (observation, Stamp(1.251, ClockDomain.SIM), ResultCode.STALE),
                (observation, Stamp(0.999, ClockDomain.SIM), ResultCode.STALE),
                (observation, Stamp(1.0, ClockDomain.WALL), ResultCode.CLOCK_MISMATCH),
                (
                    replace(observation, observed_at=Stamp(1.0, ClockDomain.WALL)),
                    Stamp(1.0, ClockDomain.SIM),
                    ResultCode.CLOCK_MISMATCH,
                ),
                (
                    replace(observation, frame_id="unregistered"),
                    Stamp(1.0, ClockDomain.SIM),
                    ResultCode.FRAME_MISMATCH,
                ),
                (
                    replace(observation, ttl_seconds=0.0),
                    Stamp(1.0, ClockDomain.SIM),
                    ResultCode.PRECONDITION_FAILED,
                ),
            )
            for index, (candidate, now, expected) in enumerate(variations):
                with self.subTest(frame=frame, variant=index):
                    self.assertEqual(candidate.validate(now), expected)
                    cases += 1
        self.assertEqual(cases, 64)

    def test_48_policy_authorization_cases(self) -> None:
        cases = 0
        gateway = GoalGateway()
        for operator in (
            "operator-a",
            "operator-b",
            "operator-c",
            "operator-d",
            "operator-e",
            "operator-f",
        ):
            goal = GoalRequest("mission", "object-00", "station", operator)
            variants = (
                (goal, False, ResultCode.OK),
                (goal, True, ResultCode.APPROVAL_REQUIRED),
                (replace(goal, approved_restricted_zone=True), True, ResultCode.OK),
                (
                    replace(goal, approved_manipulation=True),
                    True,
                    ResultCode.APPROVAL_REQUIRED,
                ),
                (replace(goal, mission_id=""), False, ResultCode.POLICY_DENIED),
                (replace(goal, target_id=""), False, ResultCode.POLICY_DENIED),
                (replace(goal, station_id=""), False, ResultCode.POLICY_DENIED),
                (replace(goal, requested_by=""), False, ResultCode.POLICY_DENIED),
            )
            for index, (candidate, restricted, expected) in enumerate(variants):
                with self.subTest(operator=operator, variant=index):
                    decision = gateway.intake(candidate, restricted_zone=restricted)
                    self.assertEqual(decision.code, expected)
                    self.assertEqual(decision.allowed, expected == ResultCode.OK)
                    cases += 1
        self.assertEqual(cases, 48)

    def test_24_development_mission_replays_are_equivalent(self) -> None:
        cases = 0
        for index in range(24):
            path = ROOT / "scenarios" / "development" / f"mission-{index:03d}.json"
            scenario = scenario_from_dict(json.loads(path.read_text(encoding="utf-8")))
            with self.subTest(scenario=scenario.scenario_id):
                record = build_record(
                    scenario, run_mission(scenario), profile_sha256="matrix"
                )
                self.assertTrue(verify_record(record))
                self.assertTrue(
                    replay_equivalent(scenario, record, profile_sha256="matrix")
                )
                cases += 1
        self.assertEqual(cases, 24)


if __name__ == "__main__":
    unittest.main()
