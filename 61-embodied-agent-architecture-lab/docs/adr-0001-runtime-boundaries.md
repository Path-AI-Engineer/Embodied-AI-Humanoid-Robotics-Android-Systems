# ADR 0001 — Runtime profile and trust boundaries

Status: accepted for the portable reference and headless ROS/Gazebo smoke; full ROS integration remains pending.

On 2026-09-25 the official ROS listing identified Lyrical as the ROS 2 release for Ubuntu 26.04, and Gazebo listed Jetty as its pairing. The official `ros:lyrical-ros-base-resolute` amd64 image was pulled and executed, yielding Ubuntu 26.04.1 and a working `ros2` CLI. A clean build compiled all four Astra ROS packages, expanded the Xacro, validated the SDF world, and spawned the entity in headless Gazebo with the robot-state publisher and sensor bridges running. MoveIt 2 and BehaviorTree.CPP mission integration have not been demonstrated.

The base image carried August ROS libraries while new geometry/bridge packages came from September. That initially caused missing `has_buffer_fields_*` symbols. Updating the complete Lyrical package cohort before compiling removed the ABI failure. The `ros-smoke.ps1` gate now checks for process deaths and an actual entity-spawn success marker. This is a dated package cohort, not an immutable apt snapshot; release reproducibility still needs a frozen image digest and conformance rerun.

The Windows host has Docker Desktop Linux. The portable Python harness runs headless without ROS. ROS/Gazebo packages must be built and tested in one container profile. No Jazzy/Harmonic package is mixed into the selected profile. Any profile change needs a new ADR and complete conformance rerun.

Trust boundaries:

1. Simulation owns hidden ground truth and exposes sensor observations only. Scoring gets a separate object that is never passed into the agent runtime.
2. Goal gateway checks typed goals and approvals; planner does not bypass it.
3. Skills are allowlisted and validate fresh beliefs before motion.
4. Only the control gateway can commit motor commands. Safety supervisor approves every command independently and latches E-stop.
5. Evidence includes typed events, a terminal outcome and a SHA-256 checksum. Test scenarios are locked until the protocol is frozen.

This architecture does not provide hard real-time guarantees or certified physical safety. Hardware integration is outside this project gate.

Sources checked: [ROS getting started](https://www.ros.org/blog/getting-started/), [Gazebo ROS installation](https://gazebosim.org/docs/garden/ros_installation/), [Gazebo bridge documentation](https://gazebosim.org/docs/latest/ros2_integration/).
