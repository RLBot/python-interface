from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager
from rlbot.utils.gateway import find_file
from rlbot.utils.os_detector import RLBOT_SERVER_NAME

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "human_vs_atba.toml"
RLBOT_SERVER_PATH = find_file(DIR / "../../core/RLBotCS/bin/Release/", RLBOT_SERVER_NAME)

if __name__ == "__main__":
    with MatchManager(RLBOT_SERVER_PATH) as man:
        man.start_match(MATCH_CONFIG_PATH)
        assert man.packet is not None

        # wait for the match to end
        while man.packet.match_info.match_phase != flat.MatchPhase.Ended:
            sleep(1.0)
