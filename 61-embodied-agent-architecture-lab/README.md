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

Set `PYTHONPATH=src` when invoking Python directly. The PowerShell gate configures it automatically. The quality gate checks Ruff, 64 development scenarios, Python tests, TypeScript, ESLint, the production build, and desktop/mobile Playwright. `scenarios/test` is held out until the protocol and runtime are frozen. The ROS 2 package, Gazebo world, and control integration are separate from the portable headless reference and need their own runtime gate. A green portable/web gate alone is not ROS/Gazebo conformance or full project closure.

The local API binds only to `127.0.0.1:8161`; the workbench runs at `127.0.0.1:8162`. Its replay endpoint accepts only registered development fixtures, not arbitrary motor commands. The sample simulator is a same-process research harness, not a security boundary against malicious Python in the process.

## Verification boundary

Verified locally: 64 development fixtures with deterministic evidence, unit/API and desktop/mobile UI tests; seven compiled ROS packages; interface/Xacro/SDF checks; 12 clean Astra headless bringups on the current observation/policy/safety revision; lifecycle-managed lidar and world-model nodes with configure/activate/deactivate/reactivate smoke; lidar-derived percepts feeding the independent world model; typed goal policy checks; a C++ motor-command safety gateway that requires fresh world facts and a same-mission policy decision, with E-stop, explicit recovery and velocity rejection; rosbag2 checks that no nonzero gateway command is published between E-stop and recovery; and a separate SROS2 positive/negative publisher fixture. The ROS bag check is an event-order/invariant check, not exact deterministic ROS replay.

Not yet verified: a complete ROS mission with coordinated lifecycle rollback and cancellable skills; MoveIt/BehaviorTree.CPP/ros2_control execution; SROS2 enforcement for the entire launch graph (the default launch is still a trusted local graph); 32 held-out tests after protocol freeze; or approval of the verified `embodied-architecture-contracts-v1` technical candidate by both routes. The `approved_restricted_zone` Boolean alone is deliberately rejected as authorization. This repository is not yet a finished Project 61 release.

## Boundaries

`astra_simulation` owns synthetic observations and scoring truth. The separate `lidar_perception` and `world_model` ROS processes validate frame, clock and freshness and maintain short-lived facts. `embodied_goals` denies unsigned restricted-zone approval. The portable executive/skill path still needs ROS integration. `embodied_safety` authorizes bounded motor commands and latches stops; without SROS2 enforcement it is not yet a cryptographically exclusive publisher. The portable `embodied.evidence` module owns checksummed run records. The workbench reads evidence and runs registered synthetic fixtures; it cannot publish motor commands.

The previous `61-embodied-ai-foundations-lab` README remains in the repository as historical conceptual material. This implementation follows the newer Project 61 map and does not import earlier project code.
