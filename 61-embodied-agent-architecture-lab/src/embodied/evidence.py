"""Canonical, checksummed mission evidence with replay verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .contracts import SCHEMA_VERSION
from .executive import MissionResult
from .simulation import Scenario


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def build_record(
    scenario: Scenario, result: MissionResult, *, profile_sha256: str
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario": asdict(scenario),
        "profile_sha256": profile_sha256,
        "robot_revision": "astra-synthetic-v1",
        "world_revision": "embodied-lab-v1",
        "plan_revision": "deterministic-reference-v1",
        "clock_domain": "sim",
        "outcome": result.outcome,
        "reason": result.reason,
        "safety_mode": result.safety_mode,
        "events": result.events,
        "score": result.score,
    }
    return {"payload": payload, "sha256": digest(payload)}


def write_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(record))
    temporary.replace(path)


def verify_record(record: dict[str, object]) -> bool:
    payload = record.get("payload")
    if not isinstance(payload, dict) or record.get("sha256") != digest(payload):
        return False
    events = payload.get("events")
    return bool(
        isinstance(events, (list, tuple))
        and events
        and events[-1].get("kind") == "terminal"
    )


def replay_equivalent(
    scenario: Scenario, record: dict[str, object], *, profile_sha256: str
) -> bool:
    from .executive import run_mission

    # Evidence is persisted as canonical JSON. Python tuples in an in-memory
    # mission become lists when read back; compare the persisted representation.
    return canonical(record) == canonical(
        build_record(scenario, run_mission(scenario), profile_sha256=profile_sha256)
    )
