from setuptools import setup
from glob import glob

package_name = "pawai_brain"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name, f"{package_name}.nodes"],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=[
        "setuptools",
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "PyYAML>=5.4",
    ],
    zip_safe=True,
    maintainer="roy",
    maintainer_email="roy422roy@gmail.com",
    description="PawAI Conversation Engine — LangGraph primary runtime.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "conversation_graph_node = pawai_brain.conversation_graph_node:main",
        ],
    },
)
