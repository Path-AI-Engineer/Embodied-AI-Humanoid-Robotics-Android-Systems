"""Fail-closed test-split lock bound to an explicit source/scenario snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "data" / "manifests" / "evaluation-freeze.v1.json"
SCOPE = (
    ".dockerignore",
    "Dockerfile.ros",
    "pyproject.toml",
    "apps/workbench/package.json",
    "apps/workbench/package-lock.json",
    "apps/workbench/next.config.ts",
    "apps/workbench/playwright.config.ts",
    "apps/workbench/tsconfig.json",
    "apps/workbench/eslint.config.mjs",
)
TREES = (
    "configs",
    "contracts",
    "apps/workbench/app",
    "apps/workbench/tests",
    "src",
    "astra_interfaces",
    "astra_description",
    "astra_simulation",
    "astra_moveit_config",
    "astra_bringup",
    "embodied_observation",
    "embodied_goals",
    "embodied_skills",
    "embodied_executive",
    "embodied_safety",
    "scripts",
    "scenarios/development",
    "scenarios/test",
    "tests",
)
EXCLUDED_PARTS = {"__pycache__", "node_modules", ".venv", "build", "install", "log"}


def snapshot() -> dict[str, str]:
    paths = [ROOT / item for item in SCOPE]
    for tree in TREES:
        paths.extend(
            path
            for path in (ROOT / tree).rglob("*")
            if path.is_file()
            and not (set(path.relative_to(ROOT).parts) & EXCLUDED_PARTS)
        )
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(set(paths))
    }


def require_test_freeze() -> None:
    if not FREEZE.is_file():
        raise PermissionError(
            "test split remains locked until evaluation-freeze.v1.json exists"
        )
    try:
        manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PermissionError("evaluation freeze is unreadable") from exc
    if (
        manifest.get("schema_version") != "astra.evaluation-freeze.v1"
        or manifest.get("status") != "sealed"
        or manifest.get("files") != snapshot()
    ):
        raise PermissionError(
            "evaluation freeze does not match the current source and fixtures"
        )
