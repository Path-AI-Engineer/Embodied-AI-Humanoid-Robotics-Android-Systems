# ADR 0005 — Simulation-lab closure versus production hardening

Status: accepted for Project 61 lab-scope review, 2026-09-29.

## Context

The supplied Project 61 map requires deterministic fixture replay, rosbag **sensor** replay, an SROS2 security **baseline**, 12 clean headless bringups, 32 locked scenarios and an approved data-only handoff. The first architecture charter used stricter language, calling exact all-message rosbag equivalence and full-launch-graph SROS2 enforcement separate closure gates. That wording exceeded the map's simulation-lab scope. It must not be quietly interpreted as achieved.

## Decision

Project 61 can close as a **trusted-local, simulation-only architecture lab** when the map's gates are independently verified. The 24 deterministic fixture replays and 32 locked-run persisted replays are exact; the rosbag sensor replay is reported with matching source timestamps and coverage, including its non-identical complete fact sets. The SROS2 baseline is an isolated allow/deny fixture for a sensitive base topic and arm action. Neither result is represented as full-graph access control, deterministic all-message ROS replay, certified safety or hardware authority.

Exact all-message/decision-equivalent ROS replay, full-graph SROS2 enforcement, dynamic-obstacle occupancy validation, broader real-ROS fault injection, and a measured arm-stop latency distribution are **production-hardening gates** before exposing the graph to untrusted participants or connecting hardware. No such deployment is part of this lab release. Any future claim of those properties requires new tests and evidence, not this ADR alone.

This boundary decision changes no robot policy, fixture, scoring rule or locked test result. The initial stricter charter remains in Git history; the current charter links this explicit scope correction. The approved cross-route handoff is reference-only data and confers no command authority or direct schema compatibility.
