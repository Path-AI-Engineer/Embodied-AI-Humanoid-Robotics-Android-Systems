# Twelve clean ROS/Gazebo bringups

Status: **passed** for the local Lyrical/Jetty simulation image, then **passed
again after the independent arm-control gateway was added**. This is not a
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

## Independent arm-gateway revision

- Command: `pwsh -File scripts/ros-smoke.ps1 -SkipBuild -Runs 12`
- Image ID: `sha256:886fa985c73beab9376c0eb3972a80a6c84448e8fd2b525bd1f2e89f36a5f917`
- Result: 12/12 fresh, disposable ROS/Gazebo containers passed. Each completed
  the ten-skill mission, arm-point action through the independent gateway,
  unauthorized arm-action rejection, six-axis joint bounds, and E-stop-to-
  recovery zero-motion bag check. This campaign does **not** demonstrate
  graph-wide SROS2 enforcement, MoveIt planning, deterministic replay or
  bounded arm-stop latency.

| Run | ROS bag SQLite SHA-256 | Result |
| --- | --- | --- |
| 1 | `5c5c5c37553fc8ca4abaf5fb14d6cde9f920f02fb282196754c229d1084d089c` | PASS |
| 2 | `c97965c0a5b2de249d2f54c60550aa20c57b16d042200618a7caddc7b9914b57` | PASS |
| 3 | `8f02b922ca98546ed0d5c596175a18c51fcba76f8974d4df4bab62c023fcd9d4` | PASS |
| 4 | `e3eb40260e682d11d40002455f5fb08d55f8ea1059a09c17e3c4ce7a675a17a7` | PASS |
| 5 | `f3a668b089b3ff4dba11b9e8738e6dc9a63d23f331c9ba643e8ec6c7026ee15c` | PASS |
| 6 | `b304c988dfb3fe503685949f9ba95dea6567266535ffda57062d3cbc8532cdda` | PASS |
| 7 | `79b65fd7b4ea204833d4999667c1f9dda19780bc6a97db210ec69c52bfd1b368` | PASS |
| 8 | `65157087d9acc833f684dc04fdfbb44761a2de97becf1a07448fa333ee2f4083` | PASS |
| 9 | `ffa2f8bb15f7514e7d78053ea606c4c2fee00a8c947eb59d0833dc67823e6397` | PASS |
| 10 | `cfa306dee1679f860963f1bbdd9eb31e7699e5ab3585c396837ecf000a020fd9` | PASS |
| 11 | `8f9beddf558a874a05c50ec7cf0a5acc5d9a46fff016c878d62231a590966acf` | PASS |
| 12 | `cbcff1e887596a031caaac720cd09793892fe66aa850f5fc9d0848e91509ab08` | PASS |

The second campaign also used `docker run --rm`; these hashes identify verified
ephemeral bags, not preserved replay inputs. The source-bound held-out split
lock was committed afterwards and is not part of this ROS image.

## Retained sensor bag (additional run)

`pwsh -File scripts/ros-smoke.ps1 -SkipBuild -CaptureBag` passed on the same
gateway image. It saved one ~554 MB SQLite rosbag2 file plus metadata and probe
logs under ignored `reports/local/ros-evidence/20260926-141942-414881be/`.
The bag SHA-256 was independently rechecked on the host as
`8a82acd8192f1047644accc801a85b4134608c35063504cf6887eae57250c996`.
It contains 660 lidar scans, 1,000 RGB frames, 998 depth frames, 3,295 odometry
messages, `/clock`, one `/tf_static` sample, and the mission/safety topics.
Capture and offline invariant checks passed; sensor-driven ROS replay and
decision equivalence remain unverified.

## Sensor-driven replay

The retained bag was replayed twice into fresh lifecycle-managed lidar,
RGB-D and world-model processes using `scripts/ros-sensor-replay.ps1`.
Both runs produced new `object-00` and `obstacle/front` percepts and world facts
from **raw sensor topics**, not from replaying the original fact topics.
The second run retained its derived rosbag2, player log and verifier output in
ignored `reports/local/sensor-replay/20260926-143055-cc96ef6f/`.

| Replay | Object percepts and facts | Obstacle percepts and facts | Result |
| --- | ---: | ---: | --- |
| First | 581 | 660 | PASS |
| Second | 548 | 660 | PASS |

The different RGB-D count is evidence that this transport-level replay is
**not exact decision-equivalent**. Scheduling and frame pairing must be
controlled before claiming deterministic ROS replay. Neither replay exercised
the mission executive or motor path.
