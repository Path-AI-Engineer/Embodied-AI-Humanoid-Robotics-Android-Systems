# Project 61 contract handoff review — 2026-09-27

Candidate: `contracts/embodied-architecture-contracts-v1/manifest.json`, schema `embodied-architecture-contracts-v1`, status `technical_candidate_unapproved`. The independent verifier accepted 14 data-only files with matching sizes and SHA-256 digests. No runtime code, credentials or private bags are included.

AI Engineer evidence available for review:

- [Final portable evaluation](../reports/final-evaluation-2026-09-27.md): 32 held-out scenarios, zero unsafe motor commands, valid terminal manifests and persisted-record replay, with the freeze amendment preserved.
- [ROS/Gazebo campaign](../reports/ros-bringup-campaign-2026-09-27.md): 12/12 consecutive clean bringups on the final image, with prior failed attempts preserved separately.
- Local-only SROS2 allow/deny fixture: authorized base publisher and arm-action client accepted, unauthorized peers denied. This does **not** mean the default entire ROS graph is security-enforced.
- Fresh rosbag sensor replay: matching source-timestamp facts, not exact fact-set equivalence.

Software Engineer review must independently validate the interface catalog, ROS message/action schemas, sample trace, frame/unit/time/QoS contracts, and compatibility with its own Sprint 1 visualizer. The Software route must not import this runtime, credentials or private bags. Its current Sprint 1 plan explicitly says P61 output is not incorporated before validation.

Approval remains **pending from both routes**. Do not change the manifest status, publish a final release/tag, or claim cross-repository integration solely from these local checks. Prior camera-readiness failures, non-exact sensor replay, and the distinction between the isolated SROS2 fixture and an enforced full graph are material review notes.
