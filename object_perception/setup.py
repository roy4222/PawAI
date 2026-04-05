from glob import glob

from setuptools import setup

package_name = "object_perception"

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
    install_requires=["setuptools", "numpy", "opencv-python"],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS2 object detection: YOLO26n ONNX on D435 RGB",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "object_perception_node = object_perception.object_perception_node:main",
        ],
    },
)
