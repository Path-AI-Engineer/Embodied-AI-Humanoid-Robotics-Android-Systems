cmake_minimum_required(VERSION 3.10)
project(astra_interfaces)
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Percept.msg"
  "msg/EntityState.msg"
  "msg/WorldDelta.msg"
  "msg/GoalRequest.msg"
  "msg/PolicyDecision.msg"
  "msg/SkillDescriptor.msg"
  "msg/SkillFeedback.msg"
  "msg/SafetyState.msg"
  "msg/FaultEvent.msg"
  "msg/EvidenceManifest.msg"
  "action/SkillInvocation.action"
  DEPENDENCIES builtin_interfaces geometry_msgs
)
ament_export_dependencies(rosidl_default_runtime)
ament_package()
