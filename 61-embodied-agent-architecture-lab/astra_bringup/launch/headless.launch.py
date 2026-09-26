"""Headless Gazebo bringup with a bounded, independent safety gateway."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    sim_share = Path(get_package_share_directory("astra_simulation"))
    description_share = Path(get_package_share_directory("astra_description"))
    bringup_share = Path(get_package_share_directory("astra_bringup"))
    gz_share = Path(get_package_share_directory("ros_gz_sim"))
    world = sim_share / "worlds" / "embodied_lab.sdf"
    model = description_share / "urdf" / "astra.urdf.xacro"
    robot_xml = __import__("subprocess").check_output(["xacro", str(model)], text=True)
    return LaunchDescription([
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gz_share / "launch" / "gz_sim.launch.py")), launch_arguments={"gz_args": f"-r -s {world}"}.items()),
        Node(package="robot_state_publisher", executable="robot_state_publisher", namespace="astra", parameters=[{"robot_description": robot_xml, "use_sim_time": True}]),
        Node(package="ros_gz_bridge", executable="parameter_bridge", name="sensor_bridge", parameters=[{"config_file": str(bringup_share / "config" / "bridge.yaml"), "use_sim_time": True}]),
        Node(package="embodied_safety", executable="safety_gateway", name="safety_gateway", parameters=[{"use_sim_time": True}], output="screen"),
        LifecycleNode(package="embodied_observation", executable="lidar_perception", name="lidar_perception", namespace="", autostart=True, parameters=[{"use_sim_time": True}], output="screen"),
        LifecycleNode(package="embodied_observation", executable="camera_perception", name="camera_perception", namespace="", autostart=True, parameters=[{"use_sim_time": True}], output="screen"),
        LifecycleNode(package="embodied_observation", executable="world_model", name="world_model", namespace="", autostart=True, parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="embodied_goals", executable="goal_gateway", name="goal_gateway", parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="embodied_skills", executable="skill_server", name="skill_server", parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="embodied_executive", executable="mission_executive", name="mission_executive", parameters=[{"use_sim_time": True}], output="screen"),
        ExecuteProcess(cmd=["ros2", "run", "ros_gz_sim", "create", "-name", "astra", "-topic", "/astra/robot_description", "-x", "-2", "-y", "0", "-z", "0.3"], output="screen"),
    ])
