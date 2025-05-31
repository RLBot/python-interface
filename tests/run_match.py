from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "human_vs_atba.toml"
RLBOT_SERVER_FOLDER = DIR / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    with MatchManager(RLBOT_SERVER_FOLDER) as man:
        man.start_match(MATCH_CONFIG_PATH)
        assert man.packet is not None

        # wait for the match to end
        while man.packet.match_info.match_phase != flat.MatchPhase.Ended:
            sleep(1.0)
