from setuptools import find_packages, setup

setup(
    name="embodied_observation",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/embodied_observation"],
        ),
        ("share/embodied_observation", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Embodied Systems Lab",
    maintainer_email="engineering@example.invalid",
    description="ROS perception and temporal world model",
    license="MIT",
    entry_points={
        "console_scripts": [
            "lidar_perception = embodied_observation.perception:main",
            "world_model = embodied_observation.world:main",
        ]
    },
)
