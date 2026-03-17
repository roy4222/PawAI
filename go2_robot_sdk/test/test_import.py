"""Smoke tests: verify entry-point modules are importable."""


def test_import_main():
    from go2_robot_sdk import main  # noqa: F401


def test_import_domain_constants():
    from go2_robot_sdk.domain.constants.robot_commands import ROBOT_CMD  # noqa: F401


def test_import_domain_entities():
    from go2_robot_sdk.domain.entities.robot_config import RobotConfig  # noqa: F401
