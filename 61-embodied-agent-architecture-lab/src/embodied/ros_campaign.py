"""Validate local ROS/Gazebo evidence before exposing it in the workbench."""

from __future__ import annotations

import re
from typing import Any


def verify_campaign(
    report: dict[str, Any], *, expected_profile_sha256: str | None = None
) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("campaign must be a JSON object")
    if report.get("schema_version") != "astra.ros-bringup-campaign.v1":
        raise ValueError("unexpected campaign schema")
    results = report.get("results")
    if (
        report.get("requested_runs") != 12
        or not isinstance(results, list)
        or len(results) != 12
    ):
        raise ValueError("12 clean bringups were not recorded")
    image_id = report.get("image_id", "")
    profile_hash = report.get("robotics_profile_sha256", "")
    if not isinstance(image_id, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", image_id
    ):
        raise ValueError("campaign image digest is missing")
    if not isinstance(profile_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", profile_hash
    ):
        raise ValueError("profile lock digest is missing")
    if expected_profile_sha256 is not None and profile_hash != expected_profile_sha256:
        raise ValueError("campaign profile differs from the current locked profile")
    total_wall_seconds = 0.0
    minimum_arm_samples = None
    for index, result in enumerate(results, start=1):
        if (
            not isinstance(result, dict)
            or result.get("run") != index
            or result.get("exit_code") != 0
        ):
            raise ValueError(f"bringup {index} failed or is out of order")
        wall_seconds = result.get("wall_seconds")
        if not isinstance(wall_seconds, (int, float)) or wall_seconds <= 0:
            raise ValueError(f"bringup {index} has no elapsed time")
        total_wall_seconds += wall_seconds
        bag = result.get("rosbag_verification") or {}
        if not isinstance(bag, dict) or not isinstance(bag.get("topics"), dict):
            raise ValueError(f"bringup {index} lacks a valid rosbag summary")
        arm_samples = bag.get("arm_samples_within_limits", 0)
        if not (
            bag.get("estop_to_recovery_zero_motion") is True
            and bag.get("mission_event_sequence") == "verified"
            and bag.get("policy_and_fault_lineage") is True
            and type(arm_samples) is int
            and arm_samples > 0
            and bag.get("topics", {}).get("/astra/evidence/mission_events") == 12
        ):
            raise ValueError(f"bringup {index} lacks safety/evidence invariants")
        minimum_arm_samples = (
            arm_samples
            if minimum_arm_samples is None
            else min(minimum_arm_samples, arm_samples)
        )
    return {
        "status": "verified",
        "clean_bringups": 12,
        "image_id": image_id,
        "robotics_profile_sha256": profile_hash,
        "total_wall_seconds": round(total_wall_seconds, 3),
        "minimum_arm_samples_within_limits": minimum_arm_samples,
        "estop_to_recovery_zero_motion": True,
        "mission_event_sequence": "verified",
        "evidence_kind": "live_ros_gazebo",
    }
