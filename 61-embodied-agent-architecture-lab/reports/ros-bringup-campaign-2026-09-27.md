# Project 61 clean ROS/Gazebo campaign — 2026-09-27

The final local `scripts/ros-smoke.ps1 -SkipBuild -Runs 12 -Image embodied-project61-ros:policy-bag` campaign completed **12/12** consecutive clean headless bringups on image `sha256:1568902b3d7b40bbcf5fe79761a0d0117a08a9bcb99a75bbdcc31056d3feed14`, with robotics profile SHA-256 `ef733ba28236b9599d068990a50346d32999cf6a7473f1de7e15189cd34a3db1`. The independent validator accepted and promoted `reports/local/ros-bringup-campaign/final.json`; this raw report is intentionally Git-ignored. Total wall time: 1478.396 seconds.

| Run | Wall seconds | Arm samples within limits | Rosbag SHA-256 |
| ---: | ---: | ---: | --- |
| 1 | 119.208 | 42696 | `507a026606d18e8aabc310b20c1b436cf734e9e3000bf63cc2fbeff1a99a85d2` |
| 2 | 129.872 | 43734 | `ad79862ceaa8f5178d3b21460c14efe2674094f656f504cd68047d305b9d0f1c` |
| 3 | 122.410 | 45762 | `02044fa3770814647adab35ddd4c3df7066f9e3f47e0f37426354380fd1a17db` |
| 4 | 128.005 | 44640 | `7e9eb1e396258b613a9d58380a972205f0986564fe6842b40a32dfc03e346648` |
| 5 | 113.955 | 43548 | `ba966f9938d3b59813c99deaebca7a672f33667615aa2119489f53ad75952f7d` |
| 6 | 113.972 | 43134 | `2e8ee42ab005e317820d4c8666919fcd33ea2f9a32f079feded7ec857dee46b7` |
| 7 | 122.120 | 43998 | `d7e32c12c72c2a7241ada7a9e25281cf0b1a07cccb94186ed0512d069c1c68d1` |
| 8 | 135.552 | 46152 | `3119a34e7bf5d51c85cb3d243c7ccfe04b6b639278d411baff64c93c0d9b0cf7` |
| 9 | 118.308 | 44052 | `ff89e002f202ed2643e4f2aa2fc27bcf80219afaabb2aca5cc7166750b7d476c` |
| 10 | 134.564 | 42936 | `9bcb455ca8ef06563e9164756baf47692ed38eb0342c1c41d58d827a90d56f91` |
| 11 | 124.859 | 44490 | `183edd5aa738c77eb73d56b3e81b7ff96df1d3369705e58fff133a71c3cc8644` |
| 12 | 115.571 | 44562 | `9157e9072adb3e0eea3d4eda8c3928b86adf5a9d0a5f966237f71a6586f4b3d0` |

Every run exited zero, recorded twelve ordered mission events, verified goal/policy/fault lineage, and found no nonzero authorized base command between E-stop and explicit recovery. Earlier failed attempts are retained under `reports/local/ros-bringup-campaign/` rather than erased. The final image includes separate reliable camera/LiDAR and target topics, a bounded lifecycle bootstrap, per-mission policy leases, and explicit cancellation acknowledgement.

A fresh bag capture on the final image passed (`reports/local/ros-evidence/20260927-023152-2428222d`). Its raw-sensor replay matched facts at 1,313 shared source timestamps for perception and 1,221 for world entities. Source coverage was 98.80% and 98.63%, respectively, but neither complete fact set was identical. The replay evidence is retained under `reports/local/sensor-replay/20260927-023429-3047ba85/`. This is a sensor-replay check, not exact all-message ROS replay. The SROS2 allow/deny fixture passed on the final image; full-graph SROS2 enforcement and broader real-ROS fault injection are not established.
