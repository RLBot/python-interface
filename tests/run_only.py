import sys
from pathlib import Path

from rlbot.managers import MatchManager

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "render_test.toml"
RLBOT_SERVER_FOLDER = DIR / "../"

if __name__ == "__main__":
    match_config_path = MATCH_CONFIG_PATH
    if len(sys.argv) > 1:
        match_config_path = Path(sys.argv[1])
    assert match_config_path.exists(), f"Match config not found: {match_config_path}"

    with MatchManager(RLBOT_SERVER_FOLDER) as man:
        man.start_match(match_config_path, False)

        # Wait for input
        input("\nPress enter to end the match: ")

        # End the match
        man.stop_match()
