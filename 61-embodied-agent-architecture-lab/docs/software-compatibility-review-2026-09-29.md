# Project 61 → Software Engineer 11: read-only contract review

Date: 2026-09-29. This review inspected the AI Engineer Project 61 candidate at commit `d2ca223f2bcb0c68d75175ae614d9b5d83b5f736` and the independent Software Engineer Project 11 checkout at commit `707687bd4643cc889c55b920490f4b9b4e295595`. Neither checkout was modified by the comparison. The AI handoff manifest SHA-256 is `DD4537F358E76144E47DAAF8EFDE8AA44A33BC60AE80A8512210F70968D503CA`; its 14 exported data files pass the local checksum verifier.

| Boundary | AI Engineer 61 | Software Engineer 11 | Review conclusion |
| --- | --- | --- | --- |
| Simulation clock | `sim`, timestamps in seconds in the sample trace | `gazebo_sim`, integer nanoseconds in `loop-event.v1` and `robot-state.v1` | Different contracts. Any adapter must explicitly convert units and clock labels; a direct import is invalid. |
| Evidence identity | Mission/scenario ID and ordered `events[].sequence` | Run ID, robot ID, correlation ID and `event_sequence` | A reference-only visualizer can display the AI trace, but cannot claim it is a native Software 11 run without provenance and correlation mapping. |
| Event vocabulary | `perception`, `policy`, `skill`, `safety`, `terminal` | `perception`, `state`, `memory`, `intent`, `safety`, `action`, `feedback` | No lossless one-to-one mapping. Preserve the original event kind and schema version in any derived view. |
| Robot telemetry | Astra topics, frames, QoS and ROS messages in the interface catalog | One-joint `RobotState` and `LoopEvent` contracts in the Sprint 1 visualizer | These are separate robots and runtime graphs. Do not connect control topics or import AI runtime code. |
| Authority | AI goal/policy, safety and arm gateways | Software local operator lease and C++ supervisor | Neither route's authority token or decision authorizes the other route's control path. |

The Software 11 `loop-event.v1.schema.json` and `robot-state.v1.schema.json` are SHA-256 `2CCF769C8206E6BDD5D7E8E74B5C52F0F38E5423360FAF7A758D8677FF235686` and `1461FDB301DEA8632E111F1086488E9A07B04B6A321B266D60A6A5333EF1E166`, respectively. Both fix `clock_domain` to `gazebo_sim`; the AI sample uses `sim`. Software 11's Sprint 1 plan also explicitly disallows incorporating P61 output before validation. Its current README permits only a schema/hash/provenance-validated external bundle and never imported code.

**Disposition:** technically suitable as a versioned, checksummed, reference-only contract candidate. The project owner subsequently approved this exact candidate on behalf of both routes **for reference-only use**, recorded in `../contracts/embodied-architecture-contracts-v1/approval.v1.json`. It is **not** directly schema-compatible with Software 11's live event or robot-state streams and has not been imported there. Any adapter remains a separate specification, validation and approval decision. The source bag, credentials and runtime remain outside the handoff.
