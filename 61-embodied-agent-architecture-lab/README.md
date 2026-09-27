# Embodied Systems Architecture Workbench (Project 61)

An executable, headless reference architecture for the synthetic Astra mobile manipulator. A typed goal passes through observation validation, a short-term world model, a deterministic executive, an allowlisted skill gateway, an independent safety supervisor, and a checksummed evidence manifest. The agent never receives simulator ground truth; the evaluator alone can read it.

The [architecture charter](docs/architecture-charter.md) records ownership, trust boundaries, pre-registered gates, and work that remains before release.

This is a simulation research lab. It does not claim hard real-time behavior, certified safety, or sim-to-real transfer. Hardware is not required.

## Current scope

- `pwsh -File scripts/setup.ps1` (project-local Python venv and locked web install)
- `python -m embodied.cli run --scenario scenarios/development/mission-000.json --out reports/local`
- `python -m embodied.cli evaluate --split development --out reports/local`
- `python -m unittest discover -s tests -v`
- `pwsh -File scripts/quality-gate.ps1`
- `pwsh -File scripts/ros-smoke.ps1 -SkipBuild -CaptureBag` (preserves one local sensor/evidence bag after the image has been built)
- `pwsh -File scripts/ros-sensor-replay.ps1 -EvidenceDirectory <captured-bag-directory>` (raw-sensor functional replay; derived bag saved locally)

Set `PYTHONPATH=src` when invoking Python directly. The PowerShell gate configures it automatically. The quality gate checks Ruff, 64 development scenarios, Python tests, TypeScript, ESLint, the production build, and desktop/mobile Playwright. `scenarios/test` is held out until the protocol and runtime are frozen. The ROS 2 package, Gazebo world, and control integration are separate from the portable headless reference and need their own runtime gate. A green portable/web gate alone is not ROS/Gazebo conformance or full project closure.

The local API binds only to `127.0.0.1:8161`; the workbench runs at `127.0.0.1:8162`. Its replay endpoint accepts only registered development fixtures, not arbitrary motor commands. Its ROS evidence panel reads only a fully verified, locally promoted 12-run campaign; portable fixture replay and live ROS/Gazebo evidence are labeled separately. The sample simulator is a same-process research harness, not a security boundary against malicious Python in the process.

## Verification boundary

Verified locally: 64 development fixtures with deterministic evidence; 25 Python tests covering the registered interface, fault, time, authorization, safety and replay matrices; TypeScript, lint, production build and 4 desktop/mobile Playwright tests; eight compiled ROS packages plus the MoveIt configuration package; and [12/12 consecutive clean ROS/Gazebo bringups on the final image](reports/ros-bringup-campaign-2026-09-27.md) (`sha256:1568902b3d7b40bbcf5fe79761a0d0117a08a9bcb99a75bbdcc31056d3feed14`). These runs exercise lifecycle-managed lidar, RGB-D and world-model nodes; sensor-derived target and obstacle facts; policy checks; ten live typed skill actions; safety-authorized navigation and return; MoveIt planning followed by bounded six-axis arm execution through `arm_control_gateway`; a complete BehaviorTree.CPP mission; E-stop and explicit recovery; and rosbag2 checks for arm limits and no nonzero base command while E-stop is latched. The SROS2 allow/deny fixture passed on the same image. A fresh raw-sensor replay matched 1,313 percept and 1,221 world facts at shared source timestamps, with 98.80% and 98.63% source coverage; it was not exact set equivalence. Earlier failed clean-bringup attempts remain preserved locally; the final campaign was 12/12. The planning scene has no validated dynamic-obstacle occupancy map and is not certified collision avoidance.

The [32 held-out portable tests](reports/final-evaluation-2026-09-27.md) passed on the current sealed source snapshot: 8 `SUCCESS`, 22 `STOPPED`, 2 `DENIED`, zero unsafe motor commands, valid terminal manifests and verified on-disk replay. Their summary and all 32 run hashes remain identical across the documented amendments. Not yet verified: coordinated lifecycle rollback, a broader real-ROS fault-injection campaign and exact all-message/decision-equivalent ROS replay; ROS-wide cancellation/replanning, SROS2 enforcement for the entire launch graph (the default launch is still a trusted local graph, and the raw arm controller remains reachable), an arm-stop latency distribution beyond isolated E-stop runs, or approval of the verified `embodied-architecture-contracts-v1` technical candidate by both routes. The `approved_restricted_zone` Boolean alone is deliberately rejected as authorization. This repository is not yet a finished Project 61 release.

## Boundaries

`astra_simulation` owns synthetic observations and scoring truth. The separate `lidar_perception`, `camera_perception` and `world_model` ROS processes validate frame, clock and freshness and maintain short-lived facts. `embodied_goals` denies unsigned restricted-zone approval. `embodied_skills` executes ten typed actions; base movement passes through the C++ `safety_gateway`, while `point_at` delegates to the separate `arm_control_gateway` in `embodied_safety`, which revalidates policy, safety and RGB-D facts, obtains a MoveIt plan, validates its bounds and deadline, and only then invokes the controller. This is not yet an enforced exclusive arm path; see [ADR 0003](docs/adr-0003-arm-control-boundary.md) and [ADR 0004](docs/adr-0004-moveit-planning-only.md). `embodied_executive` runs the typed mission's BehaviorTree.CPP sequence and requests `safe_stop` on failure; the portable executive remains a distinct fixture harness. `embodied_safety` authorizes bounded base motor commands and latches stops; without SROS2 enforcement it is not yet a cryptographically exclusive publisher. The portable `embodied.evidence` module owns checksummed run records. The workbench reads evidence and runs registered synthetic fixtures; it cannot publish motor commands.

The previous `61-embodied-ai-foundations-lab` README remains in the repository as historical conceptual material. This implementation follows the newer Project 61 map and does not import earlier project code.
