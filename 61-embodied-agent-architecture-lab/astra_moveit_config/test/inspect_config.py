"""Diagnostic: show the exact planner parameters loaded by MoveItConfigsBuilder."""

import json
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder


description = Path(get_package_share_directory("astra_description"))
config = (
    MoveItConfigsBuilder("astra_synthetic_v1", package_name="astra_moveit_config")
    .robot_description(file_path=str(description / "urdf" / "astra.urdf.xacro"))
    .robot_description_semantic(file_path="config/astra.srdf")
    .robot_description_kinematics()
    .joint_limits()
    .planning_pipelines(default_planning_pipeline="ompl", pipelines=["ompl"])
    .to_moveit_configs()
)
parameters = config.to_dict()
print(
    json.dumps(
        {
            key: value
            for key, value in parameters.items()
            if key in ("ompl", "planning_pipelines", "default_planning_pipeline")
        },
        sort_keys=True,
    )
)
