# Project 61 contract handoff review — 2026-09-27

Candidate: `contracts/embodied-architecture-contracts-v1/manifest.json`, schema `embodied-architecture-contracts-v1`. The candidate manifest remains immutable at status `technical_candidate_unapproved`; the separate `approval.v1.json` binds its SHA-256 and records the project owner's explicit 2026-09-29 approval for both routes **as a reference-only data bundle**. The verifier now returns `approved_reference_only` after checking that binding and all 14 data-only files. No runtime code, credentials or private bags are included. This approval is an owner attestation, not a cryptographic signature.

AI Engineer evidence available for review:

- [Final portable evaluation](../reports/final-evaluation-2026-09-27.md): 32 held-out scenarios, zero unsafe motor commands, valid terminal manifests and persisted-record replay, with the freeze amendment preserved.
- [ROS/Gazebo campaign](../reports/ros-bringup-campaign-2026-09-27.md): 12/12 consecutive clean bringups on the final image, with prior failed attempts preserved separately.
- Local-only SROS2 allow/deny fixture: authorized base publisher and arm-action client accepted, unauthorized peers denied. This does **not** mean the default entire ROS graph is security-enforced.
- Fresh rosbag sensor replay: matching source-timestamp facts, not exact fact-set equivalence.

The [read-only Software 11 compatibility review](software-compatibility-review-2026-09-29.md) identifies different clock labels, time units, event vocabularies, robot telemetry and control authorities. The candidate is suitable for reference-only review, not direct ingestion into Software 11's live schemas. Software Engineer must independently accept that boundary or require a separately specified and tested adapter. The Software route must not import this runtime, credentials or private bags. Its Sprint 1 plan explicitly says P61 output is not incorporated before validation.

The data-only reference handoff is approved for both routes. Direct ingestion, adapter implementation, runtime/code exchange and command integration are **not** approved. Do not claim cross-repository runtime integration or production security from this sign-off. Prior camera-readiness failures, non-exact sensor replay, and the distinction between the isolated SROS2 fixture and an enforced full graph remain material review notes.
