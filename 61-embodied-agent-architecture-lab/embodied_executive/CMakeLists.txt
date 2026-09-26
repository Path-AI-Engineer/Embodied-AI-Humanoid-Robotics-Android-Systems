cmake_minimum_required(VERSION 3.10)
project(embodied_executive)

find_package(ament_cmake REQUIRED)
find_package(astra_interfaces REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(mission_executive src/mission_executive.cpp)
target_link_libraries(mission_executive PRIVATE
  behaviortree_cpp::behaviortree_cpp
  rclcpp::rclcpp
  rclcpp_action::rclcpp_action
  astra_interfaces::astra_interfaces__rosidl_generator_cpp
  astra_interfaces::astra_interfaces__rosidl_typesupport_cpp
  std_msgs::std_msgs__rosidl_generator_cpp
  std_msgs::std_msgs__rosidl_typesupport_cpp
)
target_compile_features(mission_executive PUBLIC cxx_std_17)
target_compile_options(mission_executive PRIVATE -Wall -Wextra -Wpedantic)
install(TARGETS mission_executive DESTINATION lib/${PROJECT_NAME})
ament_package()
