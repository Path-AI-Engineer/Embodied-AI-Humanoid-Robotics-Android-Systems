"""Start MoveIt in planning-only mode; Astra gateway owns execution."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description():
    description = Path(get_package_share_directory("astra_description"))
    config = (
        MoveItConfigsBuilder("astra_synthetic_v1", package_name="astra_moveit_config")
        .robot_description(file_path=str(description / "urdf" / "astra.urdf.xacro"))
        .robot_description_semantic(file_path="config/astra.srdf")
        .robot_description_kinematics()
        .joint_limits()
        .planning_pipelines(default_planning_pipeline="ompl", pipelines=["ompl"])
        .planning_scene_monitor(
            publish_planning_scene=True,
            publish_geometry_updates=True,
            publish_state_updates=True,
            publish_transforms_updates=True,
        )
        .to_moveit_configs()
    )
    return LaunchDescription(
        [
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                name="move_group",
                output="screen",
                parameters=[
                    config.to_dict(),
                    {"use_sim_time": True, "allow_trajectory_execution": False},
                ],
            )
        ]
    )
