"""Verify a data-only cross-repository contract candidate without executing it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "contracts" / "embodied-architecture-contracts-v1"
APPROVAL = TARGET / "approval.v1.json"


def main() -> None:
    manifest_bytes = (TARGET / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["schema_version"] != "embodied-architecture-contracts-v1":
        raise ValueError("unexpected handoff schema")
    if manifest["status"] != "technical_candidate_unapproved":
        raise ValueError("handoff approval must be an explicit external decision")
    if manifest["runtime_code_included"] or manifest["credentials_included"]:
        raise ValueError("handoff boundary violated")
    if len(manifest["files"]) != 14:
        raise ValueError("unexpected number of handoff files")
    seen: set[str] = set()
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or entry["path"] in seen:
            raise ValueError("unsafe handoff path")
        seen.add(entry["path"])
        if relative.parts[0] not in {"astra_interfaces", "contracts", "examples"}:
            raise ValueError("handoff contains an unexpected path")
        if relative.suffix not in {".json", ".msg", ".action"}:
            raise ValueError("handoff contains a non-data file")
        data = (TARGET / relative).read_bytes()
        if len(data) != entry["bytes"]:
            raise ValueError(f"size mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"digest mismatch: {relative}")
        if relative.parts[0] in {"astra_interfaces", "contracts"}:
            upstream = ROOT / relative
            if upstream.read_bytes() != data:
                raise ValueError(f"source changed after export: {relative}")
    status = manifest["status"]
    if APPROVAL.exists():
        approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
        expected = hashlib.sha256(manifest_bytes).hexdigest()
        if approval.get("schema_version") != "embodied.contract-handoff-approval.v1":
            raise ValueError("unexpected approval schema")
        if approval.get("candidate_manifest_sha256") != expected:
            raise ValueError("approval does not bind the current candidate")
        if approval.get("decision") != "approved_reference_only":
            raise ValueError("unsupported handoff decision")
        if approval.get("approved_routes") != ["AI Engineer", "Software Engineer"]:
            raise ValueError("both route approvals are required")
        if approval.get("scope") != "versioned data-only reference bundle":
            raise ValueError("approval scope changed")
        if not approval.get("authorized_by") or not approval.get("authorized_at_utc"):
            raise ValueError("approval provenance is missing")
        required_restrictions = {
            "no runtime code or credential exchange",
            "no control-topic or action integration",
            "no direct ingestion into Software Engineer 11 live schemas",
            "any future adapter requires separate specification, validation, and approval",
        }
        if set(approval.get("restrictions", [])) != required_restrictions:
            raise ValueError("approval restrictions changed")
        status = approval["decision"]
    print(json.dumps({"status": status, "verified_files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
