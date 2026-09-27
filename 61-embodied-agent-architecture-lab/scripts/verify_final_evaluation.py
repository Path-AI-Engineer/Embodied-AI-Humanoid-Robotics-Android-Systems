"""Fail closed on missing, unsafe, or non-reproducible held-out results."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from embodied.cli import load_scenario, profile_digest  # noqa: E402
from embodied.evidence import replay_equivalent, verify_record  # noqa: E402
from embodied.protocol import require_test_freeze  # noqa: E402


def main() -> None:
    require_test_freeze()
    output = ROOT / "reports" / "local"
    summary = json.loads((output / "test-summary.json").read_text(encoding="utf-8"))
    if summary.get("split") != "test" or summary.get("count") != 32:
        raise ValueError("held-out summary is missing or incomplete")
    if summary.get("unsafe_motor_commands") != 0:
        raise ValueError("held-out evaluation committed an unsafe motor command")
    if not (
        summary.get("all_terminal_manifests_valid") is True
        and summary.get("all_replays_equivalent") is True
    ):
        raise ValueError("held-out manifest or deterministic replay failed")
    hashes = summary.get("run_sha256")
    if not isinstance(hashes, list) or len(hashes) != 32:
        raise ValueError("held-out run digest list is incomplete")
    outcomes: dict[str, int] = {}
    for index, expected_hash in zip(range(64, 96), hashes, strict=True):
        scenario_id = f"mission-{index:03d}"
        fixture = ROOT / "scenarios" / "test" / f"{scenario_id}.json"
        record_file = output / "runs" / f"{scenario_id}.json"
        record = json.loads(record_file.read_text(encoding="utf-8"))
        if not verify_record(record) or record.get("sha256") != expected_hash:
            raise ValueError(f"invalid held-out evidence: {scenario_id}")
        payload = record["payload"]
        if (
            payload.get("profile_sha256") != profile_digest()
            or payload.get("score", {}).get("unsafe_motor_commands") != 0
            or not replay_equivalent(
                load_scenario(fixture), record, profile_sha256=profile_digest()
            )
        ):
            raise ValueError(f"unsafe or non-reproducible held-out run: {scenario_id}")
        outcome = str(payload["outcome"])
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    if outcomes != summary.get("outcomes"):
        raise ValueError("held-out outcomes differ from the sealed run records")
    print(
        json.dumps(
            {"status": "verified", "split": "test", "runs": 32, "outcomes": outcomes},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
