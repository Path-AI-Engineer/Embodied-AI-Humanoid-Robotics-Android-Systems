from setuptools import find_packages, setup

setup(
    name="embodied_skills",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/embodied_skills"]),
        ("share/embodied_skills", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Embodied Systems Lab",
    maintainer_email="engineering@example.invalid",
    description="Typed and cancellable Astra skill action gateway",
    license="MIT",
    entry_points={"console_scripts": ["skill_server = embodied_skills.server:main"]},
)
