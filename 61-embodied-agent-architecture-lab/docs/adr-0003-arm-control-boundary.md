# ADR 0003 — Simulated arm control remains a restricted prototype

Status: accepted for local simulation experiments; not approved for release.

The six Astra arm joints are exposed through `gz_ros2_control` and an active
`JointTrajectoryController`. The `point_at` skill sends one bounded, two-second
joint-space trajectory only after a fresh RGB-D target, mission policy and an
operator-armed safety state are observed. During execution it sends zero base
intent as a heartbeat, monitors those conditions and requests cancellation on
loss. Trajectory terminal paths disarm the base. The ROS smoke verifies the action
outcome and every recorded arm position and velocity sample against the URDF
limits. Gazebo's joint limiter may report a clamped command; the smoke counts
these reports and fails above its threshold or for any other launch error.

This does **not** create an independent safety supervisor for the arm. An
authorized participant on the current trusted ROS graph can invoke the raw
controller action without passing through `embodied_skills`; a best-effort
cancel cannot guarantee immediate actuator stop. The fixed trajectory is not
MoveIt planning, collision avoidance or a physical-human safety claim.

Release requires an arm-control gateway owned by the safety boundary, action
access control enforced across the complete SROS2 launch graph, bounded stop
latency under injected faults, and replay evidence for controller outcomes.
Until those are verified, this implementation is limited to local headless
simulation and must not be connected to hardware.
