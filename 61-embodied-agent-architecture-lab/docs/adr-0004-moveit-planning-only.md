# ADR 0004 — MoveIt planning with independent execution authority

Status: accepted for local, headless simulation; not a release or hardware approval.

The locked Lyrical/Jetty profile now includes the four pinned MoveIt packages in
`robotics-profile.lock`. `astra_moveit_config` provides the six-joint arm group,
SRDF self-collision exclusions, joint limits, kinematics and OMPL planning
pipeline. The profile change was made because a fixed joint-space trajectory
was insufficient to demonstrate the requested planning boundary.

`move_group` is started for planning only. It has no controller-manager plugin
configuration and cannot execute a trajectory through MoveIt's action path.
`arm_control_gateway` requests a plan from `/plan_kinematic_path`, checks the
returned joint set, endpoint, bounds and deadline, then independently submits
the trajectory to the Gazebo-backed controller after rechecking live mission
policy, RGB-D target and safety state. It cancels on authorization loss or
operator cancel. The gateway remains a prototype, not exclusive ROS-graph
access control; an otherwise authorized participant could address the raw
controller until complete SROS2 policies are enforced.

The planning scene currently models the synthetic robot and static URDF
geometry. It has no 3D occupancy sensor plugin or validated dynamic-obstacle
mapping. A successful simple point plan does **not** prove collision avoidance
around humans, dynamic obstacles, or real hardware. The simulated E-stop
probe checks cancellation and observed arm settling, not a hard stop bound.

Conformance rerun: the updated Docker image compiled; a fresh ROS/Gazebo smoke
completed a MoveIt six-joint plan, E-stop injection, all ten live skills,
mission events and rosbag invariants. The separate 12-clean-bringup campaign
and full local quality gate are recorded independently when complete.
