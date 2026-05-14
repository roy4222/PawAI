from glob import glob

from setuptools import find_packages, setup

package_name = "interaction_executive"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="Thin interaction orchestrator — state machine for demo control",
    license="MIT",
    entry_points={
        "console_scripts": [
            "interaction_executive_node = interaction_executive.interaction_executive_node:main",
            "brain_node = interaction_executive.brain_node:main",
        ],
    },
)
