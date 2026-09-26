import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from embodied.contracts import (
    ClockDomain,
    Decision,
    GoalRequest,
    MotorCommand,
    Observation,
    ResultCode,
    SafetyMode,
    Stamp,
)
from embodied.cli import evaluate, run
from embodied.evidence import build_record, replay_equivalent, verify_record
from embodied.executive import run_mission
from embodied.runtime import GoalGateway
from embodied.safety import SafetySignals, SafetySupervisor
from embodied.protocol import require_test_freeze
from embodied.simulation import AstraSimulator, Scenario, ScoringChannel


ROOT = Path(__file__).resolve().parents[1]
BASE = Scenario("unit-success", 6100, "object-00", "inspection-station", 1.0, 0.5)


class ContractTests(unittest.TestCase):
    def test_test_freeze_rejects_unsealed_or_mismatched_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "evaluation-freeze.v1.json"
            with patch("embodied.protocol.FREEZE", manifest):
                with self.assertRaises(PermissionError):
                    require_test_freeze()
                manifest.write_text(
                    json.dumps(
                        {
                            "schema_version": "astra.evaluation-freeze.v1",
                            "status": "sealed",
                            "files": {"src/embodied/cli.py": "forged"},
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaises(PermissionError):
                    require_test_freeze()

    def test_clock_frame_and_freshness_are_explicit(self) -> None:
        valid = Observation(
            "rgbd",
            "object-00",
            "map",
            Stamp(1, ClockDomain.SIM),
            0.25,
            0.95,
            0.01,
            1.0,
            2.0,
        )
        self.assertEqual(valid.validate(Stamp(1.1, ClockDomain.SIM)), ResultCode.OK)
        self.assertEqual(valid.validate(Stamp(1.3, ClockDomain.SIM)), ResultCode.STALE)
        self.assertEqual(
            replace(valid, frame_id="bad-frame").validate(Stamp(1.1, ClockDomain.SIM)),
            ResultCode.FRAME_MISMATCH,
        )
        self.assertEqual(
            replace(valid, observed_at=Stamp(1, ClockDomain.WALL)).validate(
                Stamp(1.1, ClockDomain.SIM)
            ),
            ResultCode.CLOCK_MISMATCH,
        )

    def test_catalog_has_required_contract_fields(self) -> None:
        catalog = json.loads(
            (ROOT / "contracts/interface-catalog.v1.json").read_text(encoding="utf-8")
        )
        names = {entry["name"] for entry in catalog["interfaces"]}
        self.assertEqual(len(names), 12)
        for entry in catalog["interfaces"]:
            for required in (
                "owner",
                "frame",
                "units",
                "freshness_ms",
                "deadline_ms",
                "qos",
                "result_codes",
            ):
                self.assertIn(required, entry)
            self.assertLessEqual(entry["qos"]["depth"], 16)


class SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor = SafetySupervisor()
        self.now = Stamp(1.0, ClockDomain.SIM)
        self.assertTrue(self.supervisor.self_check(SafetySignals(), self.now).allowed)
        self.assertTrue(self.supervisor.activate().allowed)

    def command(self, **changes):  # type: ignore[no-untyped-def]
        command = MotorCommand(0.2, 0, 0, self.now, Stamp(1.1, ClockDomain.SIM))
        return replace(command, **changes)

    def test_estop_is_latched_until_operator_rechecks(self) -> None:
        self.supervisor.emergency_stop(self.now)
        self.assertEqual(
            self.supervisor.authorize(self.command(), SafetySignals(), self.now).code,
            ResultCode.E_STOP_LATCHED,
        )
        self.assertFalse(
            self.supervisor.request_recovery(
                operator_authorized=False, now=self.now
            ).allowed
        )
        self.assertTrue(
            self.supervisor.request_recovery(
                operator_authorized=True, now=self.now
            ).allowed
        )
        self.assertEqual(self.supervisor.mode, SafetyMode.INIT)
        self.assertFalse(
            self.supervisor.authorize(self.command(), SafetySignals(), self.now).allowed
        )
        self.assertTrue(self.supervisor.self_check(SafetySignals(), self.now).allowed)

    def test_gateway_bypass_and_speed_exceedance_stop(self) -> None:
        denied = self.supervisor.authorize(
            self.command(origin="planner"), SafetySignals(), self.now
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(self.supervisor.mode, SafetyMode.PROTECTIVE_STOP)

    def test_human_proximity_stop(self) -> None:
        denied = self.supervisor.authorize(
            self.command(), SafetySignals(human_distance_m=0.2), self.now
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(self.supervisor.mode, SafetyMode.PROTECTIVE_STOP)

    def test_command_deadline(self) -> None:
        denied = self.supervisor.authorize(
            self.command(deadline_at=Stamp(0.9, ClockDomain.SIM)),
            SafetySignals(),
            self.now,
        )
        self.assertEqual(denied.code, ResultCode.DEADLINE_MISSED)

    def test_nonfinite_motion_and_telemetry_fail_closed(self) -> None:
        denied = self.supervisor.authorize(
            self.command(linear_mps=math.nan), SafetySignals(), self.now
        )
        self.assertEqual(denied.code, ResultCode.SAFETY_STOP)
        self.assertEqual(self.supervisor.mode, SafetyMode.PROTECTIVE_STOP)

        fresh = SafetySupervisor()
        self.assertFalse(
            fresh.self_check(SafetySignals(human_distance_m=math.nan), self.now).allowed
        )
        self.assertEqual(fresh.mode, SafetyMode.PROTECTIVE_STOP)


class MissionTests(unittest.TestCase):
    def test_locked_test_split_rejects_direct_run_and_evaluation(self) -> None:
        with patch("embodied.cli.load_scenario") as load:
            with self.assertRaises(PermissionError):
                run(ROOT / "scenarios/test/mission-064.json", ROOT / "reports/local")
            with self.assertRaises(PermissionError):
                run(
                    ROOT / "scenarios/test/mission-064.json",
                    ROOT / "reports/local",
                    unlock_test=True,
                )
            load.assert_not_called()
        with self.assertRaises(PermissionError):
            evaluate("test", ROOT / "reports/local", unlock_test=False)
        with self.assertRaises(PermissionError):
            evaluate("test", ROOT / "reports/local", unlock_test=True)

    def test_direct_motor_commit_is_rejected(self) -> None:
        simulator = AstraSimulator(BASE)
        with self.assertRaises(PermissionError):
            simulator.commit_motor_command(
                Decision(True, ResultCode.OK, "forged"), gateway=object()
            )
        score = ScoringChannel(simulator).score("STOPPED")
        self.assertEqual(score["motor_commands"], 0)
        self.assertEqual(score["unauthorized_motor_attempts"], 1)

    def test_success_has_terminal_evidence_and_replays(self) -> None:
        result = run_mission(BASE)
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertEqual(result.score["motor_commands"], 3)
        record = build_record(BASE, result, profile_sha256="test")
        self.assertTrue(verify_record(record))
        self.assertTrue(replay_equivalent(BASE, record, profile_sha256="test"))
        record["payload"]["reason"] = "tampered"
        self.assertFalse(verify_record(record))

    def test_restricted_zone_needs_approval(self) -> None:
        denied = run_mission(replace(BASE, restricted_zone=True))
        self.assertEqual(denied.outcome, "DENIED")
        self.assertEqual(denied.score["motor_commands"], 0)
        self.assertEqual(denied.events[-1]["kind"], "terminal")
        approved = run_mission(replace(BASE, restricted_zone=True, approval=True))
        self.assertEqual(approved.outcome, "SUCCESS")

    def test_faults_stop_before_unsafe_motion(self) -> None:
        for fault in (
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
        ):
            with self.subTest(fault=fault):
                result = run_mission(replace(BASE, fault=fault))
                self.assertEqual(result.outcome, "STOPPED")
                self.assertEqual(result.score["unsafe_motor_commands"], 0)
                self.assertEqual(result.events[-1]["kind"], "terminal")
                self.assertIn(result.safety_mode, ("PROTECTIVE_STOP", "EMERGENCY_STOP"))

    def test_goal_gateway_rejects_empty_identity(self) -> None:
        decision = GoalGateway().intake(
            GoalRequest("", "target", "station", "operator"), restricted_zone=False
        )
        self.assertEqual(decision.code, ResultCode.POLICY_DENIED)


if __name__ == "__main__":
    unittest.main()
