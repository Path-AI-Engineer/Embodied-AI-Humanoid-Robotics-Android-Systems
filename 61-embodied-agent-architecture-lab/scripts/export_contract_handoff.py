"""Export a data-only, checksummed contract candidate for independent review."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from embodied.cli import profile_digest
from embodied.evidence import build_record, canonical
from embodied.executive import run_mission, scenario_from_dict


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "contracts" / "embodied-architecture-contracts-v1"


def main() -> None:
    files = [ROOT / "contracts" / "interface-catalog.v1.json"]
    files += sorted((ROOT / "astra_interfaces" / "msg").glob("*.msg"))
    files += sorted((ROOT / "astra_interfaces" / "action").glob("*.action"))
    for source in files:
        relative = source.relative_to(ROOT)
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    scenario_data = json.loads(
        (ROOT / "scenarios" / "development" / "mission-000.json").read_text(
            encoding="utf-8"
        )
    )
    scenario = scenario_from_dict(scenario_data)
    example = build_record(
        scenario, run_mission(scenario), profile_sha256=profile_digest()
    )
    example_path = TARGET / "examples" / "mission-000.evidence.json"
    example_path.parent.mkdir(parents=True, exist_ok=True)
    example_path.write_bytes(canonical(example))
    exported = [TARGET / source.relative_to(ROOT) for source in files] + [example_path]
    entries = [
        {
            "path": path.relative_to(TARGET).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in exported
    ]
    manifest = {
        "schema_version": "embodied-architecture-contracts-v1",
        "status": "technical_candidate_unapproved",
        "approval_required_from": ["AI Engineer", "Software Engineer"],
        "runtime_code_included": False,
        "credentials_included": False,
        "files": entries,
    }
    (TARGET / "manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"status": manifest["status"], "files": len(entries)}))


if __name__ == "__main__":
    main()
