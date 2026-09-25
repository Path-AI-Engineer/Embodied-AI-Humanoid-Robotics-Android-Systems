"""Verify a data-only cross-repository contract candidate without executing it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "contracts" / "embodied-architecture-contracts-v1"


def main() -> None:
    manifest = json.loads((TARGET / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != "embodied-architecture-contracts-v1":
        raise ValueError("unexpected handoff schema")
    if manifest["status"] != "technical_candidate_unapproved":
        raise ValueError("handoff approval must be an explicit external decision")
    if manifest["runtime_code_included"] or manifest["credentials_included"]:
        raise ValueError("handoff boundary violated")
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe handoff path")
        data = (TARGET / relative).read_bytes()
        if len(data) != entry["bytes"]:
            raise ValueError(f"size mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"digest mismatch: {relative}")
        if relative.parts[0] in {"astra_interfaces", "contracts"}:
            upstream = ROOT / relative
            if upstream.read_bytes() != data:
                raise ValueError(f"source changed after export: {relative}")
    print(
        json.dumps(
            {"status": manifest["status"], "verified_files": len(manifest["files"])}
        )
    )


if __name__ == "__main__":
    main()
