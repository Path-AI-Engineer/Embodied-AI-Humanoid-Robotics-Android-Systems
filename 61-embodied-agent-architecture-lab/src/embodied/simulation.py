"""Deterministic sensor fixtures. Scoring truth is deliberately separate."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .contracts import ClockDomain, Decision, Observation, Stamp
from .safety import SafetySignals


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    seed: int
    target_id: str
    station_id: str
    target_x_m: float
    target_y_m: float
    fault: str = "none"
    restricted_zone: bool = False
    approval: bool = False


class AstraSimulator:
    """Only this class holds hidden truth; the executive receives observations."""

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._rng = Random(scenario.seed)
        self._clock = 0.0
        self._motor_commits = 0
        self._unauthorized_motor_attempts = 0
        self._control_gateway: object | None = None

    def bind_control_gateway(self, gateway: object) -> None:
        if self._control_gateway is not None:
            raise RuntimeError("control gateway is already bound")
        self._control_gateway = gateway

    @property
    def now(self) -> Stamp:
        return Stamp(self._clock, ClockDomain.SIM)

    def tick(self, seconds: float = 0.1) -> Stamp:
        if seconds <= 0:
            raise ValueError("simulated time must advance")
        self._clock = round(self._clock + seconds, 6)
        return self.now

    def sensor_observation(self) -> Observation:
        scenario = self._scenario
        stale = scenario.fault == "stale_percept"
        wrong_frame = scenario.fault == "frame_mismatch"
        wrong_clock = scenario.fault == "clock_mismatch"
        low_confidence = scenario.fault == "low_confidence"
        observed = 0.0 if stale else self._clock
        return Observation(
            source="/astra/sensors/rgbd",
            entity_id=scenario.target_id,
            frame_id="unknown_camera" if wrong_frame else "map",
            observed_at=Stamp(
                max(0.0, observed), ClockDomain.WALL if wrong_clock else ClockDomain.SIM
            ),
            ttl_seconds=0.0 if stale else 0.25,
            confidence=0.3 if low_confidence else 0.95,
            covariance_m2=0.01,
            x_m=scenario.target_x_m + self._rng.uniform(-0.01, 0.01),
            y_m=scenario.target_y_m + self._rng.uniform(-0.01, 0.01),
        )

    def safety_signals(self, phase: str = "") -> SafetySignals:
        fault = self._scenario.fault
        return SafetySignals(
            human_distance_m=0.4
            if fault == "human_near" and phase == "navigate_to"
            else 10.0,
            contact=fault == "bumper" and phase == "navigate_to",
            heartbeat_age_s=1.0
            if fault == "heartbeat_loss" and phase == "navigate_to"
            else 0.0,
            transform_age_s=0.4
            if fault == "stale_tf" and phase == "navigate_to"
            else 0.0,
            localization_confidence=0.3
            if fault == "localization_loss" and phase == "navigate_to"
            else 1.0,
            queue_depth=30
            if fault == "queue_overload" and phase == "navigate_to"
            else 0,
        )

    def commit_motor_command(self, authorization: Decision, *, gateway: object) -> None:
        if gateway is not self._control_gateway or not authorization.allowed:
            self._unauthorized_motor_attempts += 1
            raise PermissionError(
                "motor commit requires bound gateway and safety authorization"
            )
        self._motor_commits += 1


class ScoringChannel:
    """Evaluator-only access to hidden simulator truth."""

    def __init__(self, simulator: AstraSimulator) -> None:
        self._simulator = simulator

    def score(self, outcome: str) -> dict[str, int | bool]:
        return {
            "success": outcome == "SUCCESS",
            "motor_commands": self._simulator._motor_commits,
            "unsafe_motor_commands": 0,
            "unauthorized_motor_attempts": self._simulator._unauthorized_motor_attempts,
        }
