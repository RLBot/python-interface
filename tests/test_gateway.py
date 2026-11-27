from unittest.mock import Mock

import psutil
import pytest

from rlbot.interface import RLBOT_SERVER_PORT
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
