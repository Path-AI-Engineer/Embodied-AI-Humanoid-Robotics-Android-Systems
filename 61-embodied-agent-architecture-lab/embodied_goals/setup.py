from setuptools import find_packages, setup

setup(
    name="embodied_goals",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/embodied_goals"]),
        ("share/embodied_goals", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Embodied Systems Lab",
    maintainer_email="engineering@example.invalid",
    description="Deny-by-default Astra goal policy",
    license="MIT",
    entry_points={"console_scripts": ["goal_gateway = embodied_goals.gateway:main"]},
)
