from setuptools import setup, find_packages
import os
from glob import glob

package_name = "nav_capability"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config", "named_poses"), glob("config/named_poses/*.json")),
        (os.path.join("share", package_name, "config", "routes"), glob("config/routes/*.json")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="roy422",
    maintainer_email="roy422roy@gmail.com",
    description="Nav capability platform layer.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "nav_action_server_node = nav_capability.nav_action_server_node:main",
            "log_pose_node = nav_capability.log_pose_node:main",
            "state_broadcaster_node = nav_capability.state_broadcaster_node:main",
            "route_runner_node = nav_capability.route_runner_node:main",
            "capability_publisher_node = nav_capability.capability_publisher_node:main",
        ],
    },
)
