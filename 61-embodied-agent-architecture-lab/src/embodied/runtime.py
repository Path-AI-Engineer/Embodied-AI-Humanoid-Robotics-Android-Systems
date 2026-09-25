"""Perception, mission state, policy, skills, and bounded control path."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    Decision,
    GoalRequest,
    MotorCommand,
    Observation,
    ResultCode,
    Stamp,
)
from .safety import SafetySignals, SafetySupervisor
from .simulation import AstraSimulator


SKILLS = (
    "observe_area",
    "locate_entity",
    "navigate_to",
    "align_base",
    "point_at",
    "inspect_entity",
    "speak_report",
    "wait_for_clearance",
    "return_home",
    "safe_stop",
)


class PerceptionAdapter:
    def normalize(self, observation: Observation, now: Stamp) -> Decision:
        code = observation.validate(now)
        return Decision(
            code == ResultCode.OK,
            code,
            "percept accepted"
            if code == ResultCode.OK
            else f"percept rejected: {code}",
        )


@dataclass
class WorldModel:
    facts: dict[str, Observation]

    def update(self, observation: Observation, now: Stamp) -> Decision:
        decision = PerceptionAdapter().normalize(observation, now)
        if decision.allowed:
            self.facts[observation.entity_id] = observation
        return decision

    def get_fresh(self, entity_id: str, now: Stamp) -> Observation | None:
        observation = self.facts.get(entity_id)
        return (
            observation
            if observation and observation.validate(now) == ResultCode.OK
            else None
        )


class GoalGateway:
    def intake(self, goal: GoalRequest, *, restricted_zone: bool) -> Decision:
        if (
            not goal.mission_id
            or not goal.target_id
            or not goal.station_id
            or not goal.requested_by
        ):
            return Decision(
                False, ResultCode.POLICY_DENIED, "required goal field absent"
            )
        if restricted_zone and not goal.approved_restricted_zone:
            return Decision(
                False,
                ResultCode.APPROVAL_REQUIRED,
                "restricted zone requires human approval",
            )
        return Decision(True, ResultCode.OK, "goal accepted")


class ControlGateway:
    """The only component allowed to commit motor commands to the simulator."""

    def __init__(self, safety: SafetySupervisor, simulator: AstraSimulator) -> None:
        self._safety = safety
        self._simulator = simulator
        simulator.bind_control_gateway(self)

    def execute(
        self, *, linear: float, angular: float, arm: float, signals: SafetySignals
    ) -> Decision:
        now = self._simulator.now
        command = MotorCommand(
            linear, angular, arm, now, Stamp(now.seconds + 0.1, now.domain)
        )
        decision = self._safety.authorize(command, signals, now)
        if decision.allowed:
            self._simulator.commit_motor_command(decision, gateway=self)
        return decision


class SkillRegistry:
    def __init__(
        self, world: WorldModel, control: ControlGateway, simulator: AstraSimulator
    ) -> None:
        self._world = world
        self._control = control
        self._simulator = simulator

    def invoke(self, name: str, target_id: str) -> Decision:
        if name not in SKILLS:
            return Decision(
                False, ResultCode.UNKNOWN_SKILL, f"skill {name} is not allowlisted"
            )
        if (
            name in {"navigate_to", "point_at", "inspect_entity"}
            and self._world.get_fresh(target_id, self._simulator.now) is None
        ):
            return Decision(False, ResultCode.STALE, "target belief is stale")
        if name == "navigate_to":
            return self._control.execute(
                linear=0.2,
                angular=0.0,
                arm=0.0,
                signals=self._simulator.safety_signals(name),
            )
        if name == "point_at":
            return self._control.execute(
                linear=0.0,
                angular=0.0,
                arm=0.2,
                signals=self._simulator.safety_signals(name),
            )
        if name == "return_home":
            return self._control.execute(
                linear=0.2,
                angular=0.0,
                arm=0.0,
                signals=self._simulator.safety_signals(name),
            )
        return Decision(True, ResultCode.OK, f"{name} completed")
