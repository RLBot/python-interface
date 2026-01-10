import platform
from enum import IntEnum


class OS(IntEnum):
    UNKNOWN = 0
    WINDOWS = 1
    LINUX = 2


match platform.system():
    case "Windows":
        RLBOT_SERVER_NAME = "RLBotServer.exe"
        CURRENT_OS = OS.WINDOWS
    case "Linux":
        RLBOT_SERVER_NAME = "RLBotServer"
        CURRENT_OS = OS.LINUX
    case _ as unknown_os:
        from rlbot.utils.logging import get_logger

        RLBOT_SERVER_NAME = ""
        CURRENT_OS = OS.UNKNOWN

        get_logger("os_detector").warning("Unknown OS: %s", unknown_os)
