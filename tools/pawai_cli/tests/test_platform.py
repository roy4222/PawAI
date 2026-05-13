from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pawai_cli import platform as plat


def test_detect_macos():
    with patch("pawai_cli.platform._uname_system", return_value="Darwin"):
        info = plat.detect()
    assert info.kind == "macos"
    assert info.supported is True


def test_detect_linux_native():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch("pawai_cli.platform._read_proc_version", return_value="Linux 6.5.0 generic"), \
         patch("pawai_cli.platform._env_wsl_distro", return_value=""):
        info = plat.detect()
    assert info.kind == "linux"
    assert info.supported is True


def test_detect_wsl2():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch(
             "pawai_cli.platform._read_proc_version",
             return_value="Linux 5.15.146.1-microsoft-standard-WSL2",
         ), \
         patch("pawai_cli.platform._env_wsl_distro", return_value="Ubuntu"):
        info = plat.detect()
    assert info.kind == "wsl2"
    assert info.supported is True


def test_detect_wsl1():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch(
             "pawai_cli.platform._read_proc_version",
             return_value="Linux 4.4.0-19041-Microsoft (Microsoft@Microsoft.com)",
         ), \
         patch("pawai_cli.platform._env_wsl_distro", return_value="Ubuntu"):
        info = plat.detect()
    assert info.kind == "wsl1"
    assert info.supported is False


def test_detect_windows_native():
    with patch("pawai_cli.platform._uname_system", return_value="Windows"):
        info = plat.detect()
    assert info.kind == "windows_native"
    assert info.supported is False


def test_mnt_c_repo_path_rejected():
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    repo = Path("/mnt/c/Users/foo/elder_and_dog")
    err = plat.check_repo_path(info, repo)
    assert err is not None
    assert "/mnt/c" in err


def test_home_repo_path_accepted():
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    repo = Path("/home/user/elder_and_dog")
    assert plat.check_repo_path(info, repo) is None


def test_assert_supported_passes_on_macos():
    with patch(
        "pawai_cli.platform.detect",
        return_value=plat.PlatformInfo(kind="macos", supported=True, reason=""),
    ), patch("pawai_cli.platform.check_repo_path", return_value=None):
        plat.assert_supported(Path("/Users/foo/repo"))


def test_assert_supported_exits_on_windows_native(capsys):
    info = plat.PlatformInfo(
        kind="windows_native",
        supported=False,
        reason="Windows native unsupported",
    )
    with patch("pawai_cli.platform.detect", return_value=info):
        with pytest.raises(SystemExit) as excinfo:
            plat.assert_supported(Path("C:/Users/foo/repo"))
    assert excinfo.value.code == 10
    captured = capsys.readouterr()
    assert "Windows native unsupported" in captured.out
    assert "wsl --install" in captured.out


def test_assert_supported_exits_on_mnt_c(capsys):
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    with patch("pawai_cli.platform.detect", return_value=info):
        with pytest.raises(SystemExit) as excinfo:
            plat.assert_supported(Path("/mnt/c/Users/foo/repo"))
    assert excinfo.value.code == 10
    captured = capsys.readouterr()
    assert "/mnt/c" in captured.out
