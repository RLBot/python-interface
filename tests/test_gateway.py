from pathlib import Path
from unittest.mock import Mock

import psutil
import pytest

from rlbot.interface import RLBOT_SERVER_PORT
from rlbot.managers.match import MatchManager
from rlbot.utils import gateway


@pytest.mark.parametrize(
    ("args", "expected_port"),
    [
        ([], RLBOT_SERVER_PORT),
        (["23235"], 23235),
        (["23235", "23233"], 23235),
        (["23235", "--flag"], 23235),
        (["--flag"], RLBOT_SERVER_PORT),
        (["65536"], RLBOT_SERVER_PORT),
    ],
)
def test_find_server_process_uses_first_argument(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected_port: int
):
    server = Mock(spec=psutil.Process)
    server.name.return_value = "RLBotServer.exe"
    server.cmdline.return_value = ["RLBotServer.exe", *args]
    monkeypatch.setattr(gateway.psutil, "process_iter", lambda: iter([server]))

    assert gateway.find_server_process("RLBotServer.exe") == (server, expected_port)
    server.cmdline.assert_called_once_with()


def test_match_manager_matches_explicit_executable_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    exe = tmp_path / "RLBotServer.exe"
    exe.touch()
    server = Mock(spec=psutil.Process)
    server.name.return_value = exe.name
    server.cmdline.return_value = [str(exe), "23235", "23233"]
    monkeypatch.setattr(gateway.psutil, "process_iter", lambda: iter([server]))
    launch = Mock(side_effect=AssertionError("Server should not be launched twice"))
    monkeypatch.setattr(gateway, "launch", launch)

    manager = MatchManager(exe)
    manager.ensure_server_started()

    assert manager.rlbot_server_process is server
    assert manager.rlbot_server_port == 23235
    launch.assert_not_called()
