"""Versioned allowlist and pre/postcondition declarations for Astra skills."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillContract:
    name: str
    timeout_seconds: float
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    requires_human_approval: bool = False


SKILLS = {
    item.name: item
    for item in (
        SkillContract(
            "observe_area", 5, ("policy_allowed", "sensors_fresh"), ("target_observed",)
        ),
        SkillContract(
            "locate_entity",
            5,
            ("policy_allowed", "target_observed"),
            ("target_located",),
        ),
        SkillContract(
            "navigate_to",
            30,
            ("policy_allowed", "safety_ready", "odom_fresh"),
            ("station_reached",),
        ),
        SkillContract(
            "align_base",
            8,
            ("policy_allowed", "safety_ready", "target_observed"),
            ("target_aligned",),
        ),
        SkillContract(
            "point_at",
            10,
            ("policy_allowed", "safety_ready", "target_observed"),
            ("noncontact_point_complete",),
        ),
        SkillContract(
            "inspect_entity",
            5,
            ("policy_allowed", "target_observed"),
            ("inspection_recorded",),
        ),
        SkillContract(
            "speak_report",
            5,
            ("policy_allowed", "inspection_recorded"),
            ("report_emitted",),
        ),
        SkillContract(
            "wait_for_clearance",
            10,
            ("policy_allowed", "sensors_fresh"),
            ("front_clear",),
        ),
        SkillContract(
            "return_home",
            30,
            ("policy_allowed", "safety_ready", "odom_fresh"),
            ("home_reached",),
        ),
        SkillContract("safe_stop", 2, (), ("zero_intent_issued",)),
    )
}
