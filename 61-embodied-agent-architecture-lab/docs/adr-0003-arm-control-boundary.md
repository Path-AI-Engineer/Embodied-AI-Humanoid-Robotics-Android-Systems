# ADR 0003 — Simulated arm control remains a restricted prototype

Status: historical local-simulation checkpoint; planning details superseded by
[ADR 0004](adr-0004-moveit-planning-only.md); not approved for release.

The six Astra arm joints are exposed through `gz_ros2_control` and an active
`JointTrajectoryController`. The `point_at` skill now invokes an independent
`arm_control_gateway` action, not the raw controller. The gateway admits only a
typed, current mission with positive policy, fresh RGB-D target and ACTIVE
safety state, then sends one bounded, two-second joint-space trajectory. It
monitors those conditions, requests controller cancellation on loss, disarms
the base and confirms SAFE_IDLE before reporting success. The skill maintains
a zero base-intent heartbeat while awaiting the gateway result. The ROS smoke
checks a policy-bypass attempt, the action outcome and recorded arm position
and velocity samples against URDF limits. Gazebo's joint limiter may report a
clamped command; the smoke counts these reports and fails above its threshold
or for any other launch error.

This is a separate application-level control gateway, **not** an independently
enforced motor path. An authorized participant on the current trusted ROS
graph can still invoke the raw controller action without passing through it;
a best-effort cancel cannot guarantee immediate actuator stop. The fixed
trajectory is not MoveIt planning, collision avoidance or a physical-human
safety claim.

Release requires action access control enforced across the complete SROS2
launch graph, bounded stop latency under injected arm faults, and durable
replay evidence for controller outcomes.
Until those are verified, this implementation is limited to local headless
simulation and must not be connected to hardware.
