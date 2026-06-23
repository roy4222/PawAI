from setuptools import find_packages, setup

package_name = "pawai_contracts"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS-free shared truths for PawAI (skill registry / zh tables / LLM policy)",
    license="BSD-2-Clause",
)
