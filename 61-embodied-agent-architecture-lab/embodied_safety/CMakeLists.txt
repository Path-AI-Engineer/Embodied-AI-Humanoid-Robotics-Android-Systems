cmake_minimum_required(VERSION 3.10)
project(embodied_safety)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(astra_interfaces REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(safety_gateway src/safety_gateway.cpp)
target_link_libraries(safety_gateway PRIVATE
  rclcpp::rclcpp
  astra_interfaces::astra_interfaces__rosidl_generator_cpp
  astra_interfaces::astra_interfaces__rosidl_typesupport_cpp
  sensor_msgs::sensor_msgs__rosidl_generator_cpp
  sensor_msgs::sensor_msgs__rosidl_typesupport_cpp
  geometry_msgs::geometry_msgs__rosidl_generator_cpp
  geometry_msgs::geometry_msgs__rosidl_typesupport_cpp
  std_msgs::std_msgs__rosidl_generator_cpp
  std_msgs::std_msgs__rosidl_typesupport_cpp
)
target_compile_features(safety_gateway PUBLIC cxx_std_17)
target_compile_options(safety_gateway PRIVATE -Wall -Wextra -Wpedantic)
install(TARGETS safety_gateway DESTINATION lib/${PROJECT_NAME})
ament_package()
