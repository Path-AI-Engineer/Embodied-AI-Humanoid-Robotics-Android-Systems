"""Portable, deterministic runner and evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .evidence import (
    build_record,
    canonical,
    replay_equivalent,
    verify_record,
    write_record,
)
from .executive import run_mission, scenario_from_dict


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ID_RE = re.compile(r"^mission-\d{3}$")


def profile_digest() -> str:
    return hashlib.sha256(
        (ROOT / "configs" / "robotics-profile.lock").read_bytes()
    ).hexdigest()


def load_scenario(path: Path):  # type: ignore[no-untyped-def]
    return scenario_from_dict(json.loads(path.read_text(encoding="utf-8")))


def run(path: Path, output: Path, *, unlock_test: bool = False) -> dict[str, object]:
    scenario = load_scenario(path)
    if not SCENARIO_ID_RE.fullmatch(scenario.scenario_id):
        raise ValueError("scenario_id must be mission-NNN")
    if path.stem != scenario.scenario_id:
        raise ValueError("scenario ID does not match fixture filename")
    if int(scenario.scenario_id.removeprefix("mission-")) >= 64 and not unlock_test:
        raise PermissionError(
            "locked test scenario requires --unlock-test after protocol freeze"
        )
    record = build_record(
        scenario, run_mission(scenario), profile_sha256=profile_digest()
    )
    if not verify_record(record) or not replay_equivalent(
        scenario, record, profile_sha256=profile_digest()
    ):
        raise RuntimeError(
            f"invalid or non-reproducible evidence for {scenario.scenario_id}"
        )
    write_record(output / "runs" / f"{scenario.scenario_id}.json", record)
    return record


def evaluate(split: str, output: Path, *, unlock_test: bool) -> dict[str, object]:
    if split == "test" and not unlock_test:
        raise PermissionError(
            "locked test split requires --unlock-test after protocol freeze"
        )
    paths = sorted((ROOT / "scenarios" / split).glob("mission-*.json"))
    expected = 64 if split == "development" else 32
    if len(paths) != expected:
        raise RuntimeError(f"expected {expected} {split} scenarios, found {len(paths)}")
    records = [run(path, output, unlock_test=unlock_test) for path in paths]
    outcomes: dict[str, int] = {}
    for record in records:
        outcome = str(record["payload"]["outcome"])  # type: ignore[index]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    summary: dict[str, object] = {
        "split": split,
        "count": len(records),
        "outcomes": outcomes,
        "unsafe_motor_commands": sum(
            int(record["payload"]["score"]["unsafe_motor_commands"])
            for record in records
        ),  # type: ignore[index]
        "all_terminal_manifests_valid": all(
            verify_record(record) for record in records
        ),
        "all_replays_equivalent": all(
            replay_equivalent(
                load_scenario(path), record, profile_sha256=profile_digest()
            )
            for path, record in zip(paths, records)
        ),
        "run_sha256": [record["sha256"] for record in records],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{split}-summary.json").write_bytes(canonical(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("--scenario", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    one.add_argument("--unlock-test", action="store_true")
    many = sub.add_parser("evaluate")
    many.add_argument("--split", choices=("development", "test"), default="development")
    many.add_argument("--out", type=Path, required=True)
    many.add_argument("--unlock-test", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        record = run(args.scenario, args.out, unlock_test=args.unlock_test)
        print(
            json.dumps(
                {
                    "scenario_id": record["payload"]["scenario"]["scenario_id"],
                    "outcome": record["payload"]["outcome"],
                    "sha256": record["sha256"],
                }
            )
        )
    else:
        summary = evaluate(args.split, args.out, unlock_test=args.unlock_test)
        print(
            json.dumps(
                {key: value for key, value in summary.items() if key != "run_sha256"},
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
