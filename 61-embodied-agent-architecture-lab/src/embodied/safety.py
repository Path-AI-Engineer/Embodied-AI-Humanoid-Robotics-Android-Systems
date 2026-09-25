"""Independent, fail-closed command authorization and latched stops."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .contracts import (
    ClockDomain,
    Decision,
    MotorCommand,
    ResultCode,
    SafetyMode,
    Stamp,
)


@dataclass(frozen=True)
class SafetySignals:
    heartbeat_age_s: float = 0.0
    sensor_age_s: float = 0.0
    transform_age_s: float = 0.0
    human_distance_m: float = 10.0
    contact: bool = False
    localization_confidence: float = 1.0
    queue_depth: int = 0


class SafetySupervisor:
    def __init__(self) -> None:
        self.mode = SafetyMode.INIT
        self.events: list[dict[str, str | float]] = []
        self._estop_latched = False

    def self_check(self, signals: SafetySignals, now: Stamp) -> Decision:
        if self.mode != SafetyMode.INIT:
            return Decision(
                False, ResultCode.PRECONDITION_FAILED, "self-check requires INIT"
            )
        self.mode = SafetyMode.SELF_CHECK
        issue = self._monitor(signals)
        if issue:
            self._stop(SafetyMode.PROTECTIVE_STOP, issue, now)
            return Decision(False, ResultCode.SAFETY_STOP, issue)
        self.mode = SafetyMode.SAFE_IDLE
        return Decision(True, ResultCode.OK, "ready")

    def activate(self) -> Decision:
        if self.mode != SafetyMode.SAFE_IDLE or self._estop_latched:
            return Decision(False, ResultCode.SAFETY_STOP, "not in safe idle")
        self.mode = SafetyMode.ACTIVE
        return Decision(True, ResultCode.OK, "active")

    def emergency_stop(self, now: Stamp, reason: str = "operator E-stop") -> None:
        self._estop_latched = True
        self._stop(SafetyMode.EMERGENCY_STOP, reason, now)

    def protective_stop(self, now: Stamp, reason: str) -> None:
        if self.mode == SafetyMode.ACTIVE:
            self._stop(SafetyMode.PROTECTIVE_STOP, reason, now)

    def request_recovery(self, *, operator_authorized: bool, now: Stamp) -> Decision:
        if not operator_authorized:
            return Decision(
                False, ResultCode.APPROVAL_REQUIRED, "operator authorization required"
            )
        if self.mode not in (
            SafetyMode.EMERGENCY_STOP,
            SafetyMode.PROTECTIVE_STOP,
            SafetyMode.RECOVERY_REQUIRED,
        ):
            return Decision(False, ResultCode.PRECONDITION_FAILED, "nothing to recover")
        self.mode = SafetyMode.RECOVERY_REQUIRED
        self._estop_latched = False
        self.events.append(
            {
                "mode": self.mode,
                "reason": "authorized recovery requested",
                "sim_time_s": now.seconds,
            }
        )
        self.mode = SafetyMode.INIT
        return Decision(True, ResultCode.OK, "run self-check before activation")

    def authorize(
        self, command: MotorCommand, signals: SafetySignals, now: Stamp
    ) -> Decision:
        if self._estop_latched:
            return Decision(False, ResultCode.E_STOP_LATCHED, "E-stop is latched")
        if self.mode != SafetyMode.ACTIVE:
            return Decision(
                False, ResultCode.SAFETY_STOP, f"safety mode is {self.mode}"
            )
        if command.origin != "control_gateway":
            self._stop(
                SafetyMode.PROTECTIVE_STOP, "motor command bypassed gateway", now
            )
            return Decision(
                False, ResultCode.SAFETY_STOP, "unauthorized command origin"
            )
        if (
            now.domain != ClockDomain.SIM
            or command.issued_at.domain != now.domain
            or command.deadline_at.domain != now.domain
        ):
            self._stop(SafetyMode.PROTECTIVE_STOP, "clock domain mismatch", now)
            return Decision(False, ResultCode.CLOCK_MISMATCH, "clock domain mismatch")
        if (
            command.issued_at.seconds > now.seconds
            or now.seconds > command.deadline_at.seconds
            or now.seconds - command.issued_at.seconds > 0.2
        ):
            self._stop(
                SafetyMode.PROTECTIVE_STOP, "command deadline or age exceeded", now
            )
            return Decision(
                False, ResultCode.DEADLINE_MISSED, "command deadline or age exceeded"
            )
        if (
            not all(
                isfinite(v)
                for v in (
                    command.linear_mps,
                    command.angular_radps,
                    command.arm_velocity_radps,
                )
            )
            or abs(command.linear_mps) > 0.35
            or abs(command.angular_radps) > 0.8
            or abs(command.arm_velocity_radps) > 0.5
        ):
            self._stop(SafetyMode.PROTECTIVE_STOP, "velocity limit exceeded", now)
            return Decision(False, ResultCode.SAFETY_STOP, "velocity limit exceeded")
        issue = self._monitor(signals)
        if issue:
            self._stop(SafetyMode.PROTECTIVE_STOP, issue, now)
            return Decision(False, ResultCode.SAFETY_STOP, issue)
        return Decision(True, ResultCode.OK, "command authorized")

    @staticmethod
    def _monitor(signals: SafetySignals) -> str | None:
        if (
            not all(
                isfinite(v) and v >= 0
                for v in (
                    signals.heartbeat_age_s,
                    signals.sensor_age_s,
                    signals.transform_age_s,
                    signals.human_distance_m,
                    signals.localization_confidence,
                )
            )
            or signals.queue_depth < 0
        ):
            return "invalid safety telemetry"
        if signals.contact:
            return "bumper contact"
        if signals.human_distance_m < 0.8:
            return "human proximity limit"
        if signals.heartbeat_age_s > 0.5:
            return "heartbeat stale"
        if signals.sensor_age_s > 0.25:
            return "sensor stale"
        if signals.transform_age_s > 0.2:
            return "transform stale"
        if signals.localization_confidence < 0.7:
            return "localization uncertainty"
        if signals.queue_depth > 16:
            return "queue overload"
        return None

    def _stop(self, mode: SafetyMode, reason: str, now: Stamp) -> None:
        self.mode = mode
        self.events.append({"mode": mode, "reason": reason, "sim_time_s": now.seconds})
