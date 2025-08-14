from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.config import load_player_config
from rlbot.managers import MatchManager

DIR = Path(__file__).parent

BOT_PATH = DIR / "atba/atba.bot.toml"
RLBOT_SERVER_FOLDER = DIR / "../../core/RLBotCS/bin/Release/"

num_comms = set()


def handle_match_comm(comm: flat.MatchComm):
    global num_comms
    if comm.team < 2:
        num_comms.add(comm.index)


if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.rlbot_interface.match_comm_handlers.append(handle_match_comm)
    match_manager.ensure_server_started()
    match_manager.connect_and_run(
        wants_match_communications=True,
        wants_ball_predictions=False,
        close_between_matches=False,
        background_thread=False,
    )

    current_map = -1

    blue_bot = load_player_config(BOT_PATH, 0)
    orange_bot = load_player_config(BOT_PATH, 1)

    match_settings = flat.MatchConfiguration(
        launcher=flat.Launcher.Steam,
        auto_start_agents=True,
        wait_for_agents=True,
        existing_match_behavior=flat.ExistingMatchBehavior.Restart,
        game_map_upk="Stadium_P",
        instant_start=True,
        enable_state_setting=True,
        player_configurations=[
            blue_bot,
            blue_bot,
            blue_bot,
            blue_bot,
            blue_bot,
            orange_bot,
            orange_bot,
            orange_bot,
            orange_bot,
            orange_bot,
        ],
    )

    num_games = 0
    paused = False

    while not paused:
        num_games += 1
        print(f"Starting match # {num_games}")

        match_manager.start_match(match_settings, ensure_server_started=False)
        # when calling start_match, by default it will wait for the first packet
        assert match_manager.packet is not None

        sleep(2)
        num_comms.clear()
        while len(num_comms) < 10:
            # give an extra 5 seconds for the match to start before calling it a failure
            if (
                match_manager.packet.match_info.match_phase == flat.MatchPhase.Active
                and match_manager.packet.match_info.game_time_remaining < 60 * 4 + 55
            ):
                match_manager.set_game_state(commands=["Pause"])
                paused = True
                break
            sleep(1)

    print("Failed to start match. Paused and exiting.")
    match_manager.disconnect()
