# Project 61 architecture charter

Status: simulation-lab release candidate. The synthetic Astra mission is inspect–point–report–return. Hardware motion and claims of certified safety or hard real-time execution are out of scope. [ADR 0005](adr-0005-simulation-lab-closure-boundary.md) distinguishes the map's lab acceptance from production-hardening gates that the earlier charter wording conflated.

## Ownership and trust

| Boundary | Owner | Contract |
| --- | --- | --- |
| Sensor fixture to perception | `astra_simulation` → perception adapter | Source timestamp, frame, covariance, confidence and TTL are mandatory. |
| Perception to working state | World model | Facts retain provenance and expire; simulator ground truth is unavailable to the agent. |
| Goal to execution | Goal gateway → executive | Invalid or restricted goals fail closed before skill dispatch. |
| Skill to movement | Skill registry → control gateway | Allowlisted name, fresh target belief, bounded command and deadline. |
| Movement to simulator | Safety supervisor → bound control gateway | Independent authorization; E-stop latches and needs operator recovery plus self-check. |
| Runtime to evidence | Evidence writer | Every terminal run has a canonical checksum, outcome, reason and event sequence. |

The Python harness enforces these boundaries within a cooperative process. It is not isolation against malicious code running in that process. The ROS graph and hardware path require separate security and safety validation.

## Pre-registered acceptance

- All 12 interface catalog entries define owner, endpoint, frame, units, freshness, deadline, QoS and result codes.
- All 64 development fixtures terminate with verifiable evidence; 32 test fixtures remain held out until profile, robot, policy, and scoring are frozen.
- No motor commit occurs without the bound gateway and a positive safety decision. Bypass attempts and speed, age, contact, human-proximity, heartbeat, transform, localization and queue faults must be rejected or stopped.
- Clock-domain and frame mismatches are explicit errors, never silent conversion.
- The ROS/Gazebo image must compile all workspace packages, expand Astra Xacro, validate the world, and complete 12 clean headless bringups without crashed processes. Sensor-to-world, policy, safety and bag event-order probes must pass on each bringup.
- The production workbench must load local evidence and pass desktop/mobile keyboard and overflow checks.

The profile is Lyrical/Jetty only. If its clean runtime cannot pass, document the exact blocker in an ADR before considering the permitted Jazzy/Harmonic fallback. MoveIt planning-only and BehaviorTree.CPP mission sequencing are integrated into the ROS bringup, but they do not authorize direct arm-controller execution. The frozen test split, 12 clean ROS/Gazebo bringups, functional rosbag sensor replay, SROS2 allow/deny baseline, and reference-only cross-repository contract approval are distinct **lab** gates; a passing portable gate does not waive them. Exact all-message rosbag replay and full-graph SROS2 enforcement are separate **production-hardening** gates per ADR 0005. Until graph permissions are enforced, the ROS command topic and raw arm-controller action are not protected from an untrusted publisher.
