# Twelve clean ROS/Gazebo bringups

Status: **passed** for the local Lyrical/Jetty simulation image. This is not a
release approval, hardware safety result, or deterministic ROS replay result.

- Command: `pwsh -File scripts/ros-smoke.ps1 -Runs 12`
- Image ID: `sha256:6c4507ab509b9f8e1a1e9ca99e146f22aaeedde646d2ed47c733f1aa19f4cd8e`
- Image built from the Project 61 working tree after adding camera-readiness
  diagnostics to `skill_action_probe.py`.
- Each run used a fresh `docker run --rm` container, active six-axis
  controllers, ten live skills, a successful BehaviorTree.CPP mission, twelve
  ordered mission events, rosbag2 joint-limit checks, and the E-stop-to-recovery
  zero-motion invariant.
- The prior campaign stopped at bringup 3/12 because `object-00` did not appear
  before the 15-second camera prerequisite deadline. The probe now allows a
  bounded 45-second startup and reports RGB/depth frame counts on failure.

| Run | ROS bag SQLite SHA-256 | Result |
| --- | --- | --- |
| 1 | `6bfc2154c3150b2fdceb4f45641f5909b594b05530814fae2f51204dce4af8c8` | PASS |
| 2 | `4acfaca1216c09928307f2679f7721e1b0a1937518ae057446d65021fe9d0a796` | PASS |
| 3 | `b06f1cde93735290b734e1354989a32ad647651075f13f866d96e053377b7897` | PASS |
| 4 | `07b78baacd87ee19c914ad35b5deabb24844c72a9048928de8293cb109ac9bb8` | PASS |
| 5 | `5c0707f6449f36254158731709d8c245d490cbe17105e229fc6fd0c8f9557c72` | PASS |
| 6 | `4b457b5c777c704fae95c64ca27697c11e3489e6a997bbb99ef742100590c0a1` | PASS |
| 7 | `9f010b2dc079d3b47eaa531bae94b175325150bba964b41e6ddd368291070535` | PASS |
| 8 | `9cc11dbd4a7ce5a01fdeee24ed3f0fb77919b6e58fc91589686185620abcfd92` | PASS |
| 9 | `d0317075b044c018e8e3fa5196cdba2c5f04ad2a22a0749abf41cfcc1e2e4854` | PASS |
| 10 | `913b15477c73b25fe67ba65c2f2a44c9eb290e8b32afe76d8d3258c5f827702d` | PASS |
| 11 | `a9e87270bed1807f5df091f670312b2c204784955bc6c3371bc8db80358add4e` | PASS |
| 12 | `94091bf85a890e135ff201b4c795be1b0a1937518ae057446d65021fe9d0a796` | PASS |

The digests identify the ephemeral bags observed by the verifier. The bags
themselves were inside removed containers and are not a durable replay bundle.
Their differing hashes are expected from runtime timestamps and sample counts.
