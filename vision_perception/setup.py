from glob import glob

from setuptools import setup

package_name = "vision_perception"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=[
        "setuptools",
        "numpy",
    ],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS2 vision perception: gesture + pose classification",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "vision_perception_node = vision_perception.vision_perception_node:main",
            "mock_event_publisher = vision_perception.mock_event_publisher:main",
            "event_action_bridge = vision_perception.event_action_bridge:main",
            "vision_status_display = vision_perception.vision_status_display:main",
            "interaction_router = vision_perception.interaction_router:main",
        ],
    },
)
