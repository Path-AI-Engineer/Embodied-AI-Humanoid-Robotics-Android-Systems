"""Versioned contracts shared by the portable headless runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


SCHEMA_VERSION = "embodied.architecture.v1alpha1"
FRAME_IDS = frozenset(
    {
        "map",
        "odom",
        "base_link",
        "camera_link",
        "camera_optical_frame",
        "lidar_link",
        "arm_base_link",
        "tool0",
    }
)


class ClockDomain(StrEnum):
    SIM = "sim"
    WALL = "wall"
    SENSOR = "sensor"


class SafetyMode(StrEnum):
    INIT = "INIT"
    SELF_CHECK = "SELF_CHECK"
    SAFE_IDLE = "SAFE_IDLE"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    PROTECTIVE_STOP = "PROTECTIVE_STOP"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class ResultCode(StrEnum):
    OK = "OK"
    STALE = "STALE"
    FRAME_MISMATCH = "FRAME_MISMATCH"
    CLOCK_MISMATCH = "CLOCK_MISMATCH"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    SAFETY_STOP = "SAFETY_STOP"
    E_STOP_LATCHED = "E_STOP_LATCHED"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    UNKNOWN_SKILL = "UNKNOWN_SKILL"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"


@dataclass(frozen=True)
class Stamp:
    seconds: float
    domain: ClockDomain

    def __post_init__(self) -> None:
        if not isfinite(self.seconds) or self.seconds < 0:
            raise ValueError("timestamp must be finite and non-negative")


@dataclass(frozen=True)
class Observation:
    source: str
    entity_id: str
    frame_id: str
    observed_at: Stamp
    ttl_seconds: float
    confidence: float
    covariance_m2: float
    x_m: float
    y_m: float

    def validate(self, now: Stamp) -> ResultCode:
        if not isfinite(self.ttl_seconds) or not 0 < self.ttl_seconds <= 1:
            return ResultCode.PRECONDITION_FAILED
        if self.frame_id not in FRAME_IDS and not self.frame_id.startswith("object/"):
            return ResultCode.FRAME_MISMATCH
        if self.observed_at.domain != now.domain or now.domain != ClockDomain.SIM:
            return ResultCode.CLOCK_MISMATCH
        if (
            self.observed_at.seconds > now.seconds
            or now.seconds - self.observed_at.seconds > self.ttl_seconds
        ):
            return ResultCode.STALE
        if (
            not isfinite(self.confidence)
            or self.confidence < 0.7
            or self.confidence > 1
        ):
            return ResultCode.LOW_CONFIDENCE
        if self.covariance_m2 < 0 or not all(
            isfinite(v) for v in (self.x_m, self.y_m, self.covariance_m2)
        ):
            return ResultCode.PRECONDITION_FAILED
        return ResultCode.OK


@dataclass(frozen=True)
class GoalRequest:
    mission_id: str
    target_id: str
    station_id: str
    requested_by: str
    approved_restricted_zone: bool = False
    approved_manipulation: bool = False


@dataclass(frozen=True)
class MotorCommand:
    linear_mps: float
    angular_radps: float
    arm_velocity_radps: float
    issued_at: Stamp
    deadline_at: Stamp
    origin: str = field(default="control_gateway")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: ResultCode
    reason: str
