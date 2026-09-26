"""Seal the source and fixture hashes immediately before one held-out evaluation."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from embodied.protocol import FREEZE, snapshot  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acknowledge-final-freeze", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_final_freeze:
        raise SystemExit(
            "Refusing to seal early. Pass --acknowledge-final-freeze only after "
            "the implementation, gate and scoring protocol are fixed."
        )
    if FREEZE.exists():
        raise SystemExit("Evaluation freeze already exists; refusing to overwrite it.")
    files = snapshot()
    if len([name for name in files if name.startswith("scenarios/development/")]) != 64:
        raise SystemExit("Expected exactly 64 development fixtures.")
    if len([name for name in files if name.startswith("scenarios/test/")]) != 32:
        raise SystemExit("Expected exactly 32 locked test fixtures.")
    record = {
        "schema_version": "astra.evaluation-freeze.v1",
        "status": "sealed",
        "files": files,
    }
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    with FREEZE.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(record, target, sort_keys=True, separators=(",", ":"))
        target.write("\n")
    print(
        json.dumps({"status": "sealed", "files": len(files), "manifest": str(FREEZE)})
    )


if __name__ == "__main__":
    main()
