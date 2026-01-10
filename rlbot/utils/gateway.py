import socket
import subprocess
from pathlib import Path

import psutil

from rlbot.interface import RLBOT_SERVER_PORT
from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import CURRENT_OS

if CURRENT_OS != "Windows":
    import shlex


def find_file(base_dir: Path, file_name: str) -> Path | None:
    """
    Looks for a file called `file_name` in the given `base_dir` directory and its subdirectories.
    Returns the path to the file, or None if it was not found.
    """

    base_dir = base_dir.absolute().resolve()
    assert base_dir.exists() and base_dir.is_dir(), f"'{base_dir}' is not a directory!"

    # Search subdirectories for the file
    for path in base_dir.glob(f"**/{file_name}"):
        if path.is_file():
            return path

    return None


def is_port_accessible(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except:
            return False


def find_open_server_port() -> int:
    for port in range(RLBOT_SERVER_PORT, 65535):
        if is_port_accessible(port):
            return port

    raise PermissionError(
        "Unable to find a usable port for running RLBot! Is your antivirus messing you up? "
        "Check https://github.com/RLBot/RLBot/wiki/Antivirus-Notes"
    )


def launch(exe_path: Path) -> tuple[subprocess.Popen[bytes], int]:
    port = find_open_server_port()

    if CURRENT_OS == "Windows":
        args = [str(exe_path), str(port)]
    else:
        args = f"{shlex.quote(exe_path.as_posix())} {port}"  # on Unix, when shell=True, args must be a string for flags to reach the executable
    DEFAULT_LOGGER.info("Launching RLBotServer via %s", args)

    return subprocess.Popen(args, shell=True, cwd=exe_path.parent), port


def find_server_process(
    exe_name: str,
) -> tuple[psutil.Process | None, int]:
    logger = DEFAULT_LOGGER
    for proc in psutil.process_iter():
        try:
            if proc.name() != exe_name:
                continue

            args = proc.cmdline()

            if len(args) < 2:
                # server has no specified port, return default
                return proc, RLBOT_SERVER_PORT

            # read the port
            port = int(proc.cmdline()[-1])
            return proc, port
        except Exception as e:
            logger.error(
                "Failed to read the name of a process while hunting for %s: %s",
                exe_name,
                e,
            )

    return None, RLBOT_SERVER_PORT
