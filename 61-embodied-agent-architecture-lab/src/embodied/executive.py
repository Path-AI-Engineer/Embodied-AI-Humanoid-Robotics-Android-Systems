"""Bounded deterministic mission executive with observable fail-safe exits."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .contracts import GoalRequest, ResultCode, SafetyMode
from .runtime import ControlGateway, GoalGateway, SkillRegistry, WorldModel
from .safety import SafetySupervisor
from .simulation import AstraSimulator, Scenario, ScoringChannel


PLAN = (
    "observe_area",
    "locate_entity",
    "navigate_to",
    "align_base",
    "point_at",
    "inspect_entity",
    "speak_report",
    "return_home",
)


@dataclass(frozen=True)
class MissionResult:
    scenario_id: str
    outcome: str
    reason: str
    events: tuple[dict[str, object], ...]
    safety_mode: str
    score: dict[str, int | bool]


def run_mission(scenario: Scenario) -> MissionResult:
    simulator = AstraSimulator(scenario)
    scoring = ScoringChannel(
        simulator
    )  # evaluator-only; never passed to executive or skills
    safety = SafetySupervisor()
    world = WorldModel({})
    skills = SkillRegistry(world, ControlGateway(safety, simulator), simulator)
    events: list[dict[str, object]] = []
    outcome, reason = "STOPPED", "unknown"

    def record(kind: str, **details: object) -> None:
        events.append(
            {
                "sequence": len(events),
                "sim_time_s": simulator.now.seconds,
                "kind": kind,
                **details,
            }
        )

    def finish(final_outcome: str, final_reason: str) -> MissionResult:
        if safety.mode == SafetyMode.ACTIVE:
            if final_outcome == "SUCCESS":
                safety.mode = SafetyMode.SAFE_IDLE
            else:
                safety.protective_stop(simulator.now, final_reason)
        for event in safety.events:
            record("safety_event", **event)
        record("terminal", outcome=final_outcome, reason=final_reason)
        return MissionResult(
            scenario.scenario_id,
            final_outcome,
            final_reason,
            tuple(events),
            str(safety.mode),
            scoring.score(final_outcome),
        )

    try:
        readiness = safety.self_check(simulator.safety_signals(), simulator.now)
        record("safety", mode=safety.mode, code=readiness.code, reason=readiness.reason)
        if not readiness.allowed:
            reason = readiness.reason
            return finish(outcome, reason)
        goal = GoalRequest(
            scenario.scenario_id,
            scenario.target_id,
            scenario.station_id,
            "local-operator",
            scenario.approval,
        )
        policy = GoalGateway().intake(goal, restricted_zone=scenario.restricted_zone)
        record("policy", allowed=policy.allowed, code=policy.code, reason=policy.reason)
        if not policy.allowed:
            outcome, reason = "DENIED", policy.reason
            return finish(outcome, reason)
        safety.activate()
        record("safety", mode=safety.mode, code=ResultCode.OK)
        for skill in PLAN:
            simulator.tick(0.1)
            if scenario.fault == "estop" and skill == "navigate_to":
                safety.emergency_stop(simulator.now, "injected E-stop")
                record("fault", fault="estop", mode=safety.mode)
            if skill in {
                "observe_area",
                "locate_entity",
                "navigate_to",
                "point_at",
                "inspect_entity",
            }:
                observation = simulator.sensor_observation()
                perceived = world.update(observation, simulator.now)
                record(
                    "perception",
                    entity_id=observation.entity_id,
                    code=perceived.code,
                    source=observation.source,
                )
                if not perceived.allowed:
                    outcome, reason = "STOPPED", perceived.reason
                    break
            decision = skills.invoke(skill, scenario.target_id)
            record(
                "skill",
                name=skill,
                code=decision.code,
                allowed=decision.allowed,
                reason=decision.reason,
            )
            if not decision.allowed:
                outcome, reason = "STOPPED", decision.reason
                break
        else:
            outcome, reason = "SUCCESS", "mission completed"
        return finish(outcome, reason)
    finally:
        if safety.mode == SafetyMode.ACTIVE:
            safety.mode = SafetyMode.SAFE_IDLE


def scenario_from_dict(data: dict[str, object]) -> Scenario:
    allowed = set(Scenario.__dataclass_fields__)
    if set(data) != allowed:
        raise ValueError(f"scenario fields mismatch: {sorted(set(data) ^ allowed)}")
    return Scenario(**data)  # type: ignore[arg-type]


def scenario_dict(scenario: Scenario) -> dict[str, object]:
    return asdict(scenario)
