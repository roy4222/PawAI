from glob import glob

from setuptools import setup

package_name = "face_perception"

setup(
    name=package_name,
    version="1.0.0",
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
        "opencv-python",
    ],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS2 face perception package: YuNet detection + SFace recognition + IOU tracking",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "face_identity_node = face_perception.face_identity_node:main",
        ],
    },
)
