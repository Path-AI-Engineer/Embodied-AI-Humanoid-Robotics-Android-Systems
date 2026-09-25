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

Verified locally: 64 development fixtures with deterministic evidence, unit/API and desktop/mobile UI tests, four compiled ROS packages, interface/Xacro/SDF checks, and one headless Astra spawn. Not yet verified: ROS mission execution with lifecycle-managed nodes, MoveIt/BehaviorTree.CPP/ros2_control control integration, rosbag2 and SROS2 campaigns, the 32 held-out tests, 12 clean bringups, and an approved cross-repository `embodied-architecture-contracts-v1` handoff. This repository is an implementation baseline, not a finished Project 61 release.

## Boundaries

`astra_simulation` owns synthetic observations and scoring truth. `embodied_perception` validates frame, clock and freshness. `embodied_world_model` owns mission facts. `embodied_executive` owns plans; `embodied_skills` owns preconditions. `embodied_safety` alone authorizes bounded motor commands and latches stops. `embodied_evidence` owns append-only run records. The workbench reads evidence and sends typed goals; it cannot publish motor commands.

The previous `61-embodied-ai-foundations-lab` README remains in the repository as historical conceptual material. This implementation follows the newer Project 61 map and does not import earlier project code.
