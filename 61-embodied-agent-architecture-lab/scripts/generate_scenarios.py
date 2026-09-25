"""Materialize the pre-registered 64/32 mission registry."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAULTS = (
    "none",
    "none",
    "none",
    "stale_percept",
    "frame_mismatch",
    "clock_mismatch",
    "low_confidence",
    "human_near",
    "bumper",
    "heartbeat_loss",
    "stale_tf",
    "localization_loss",
    "queue_overload",
    "estop",
    "restricted_denied",
    "restricted_approved",
)


def main() -> None:
    for index in range(96):
        split = "development" if index < 64 else "test"
        fault = FAULTS[index % len(FAULTS)]
        scenario = {
            "scenario_id": f"mission-{index:03d}",
            "seed": 6100 + index % 12,
            "target_id": f"object-{index % 8:02d}",
            "station_id": "inspection-station",
            "target_x_m": round(1.0 + (index % 7) * 0.2, 2),
            "target_y_m": round(0.5 + (index % 5) * 0.1, 2),
            "fault": "none" if fault.startswith("restricted_") else fault,
            "restricted_zone": fault.startswith("restricted_"),
            "approval": fault == "restricted_approved",
        }
        path = ROOT / "scenarios" / split / f"mission-{index:03d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(scenario, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {"total": 96, "development": 64, "test_locked": 32, "world_seeds": 12}
        )
    )


if __name__ == "__main__":
    main()
