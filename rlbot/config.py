import os
import re
import tomllib
from pathlib import Path
from typing import Any, Literal

from rlbot import flat
from rlbot.utils.os_detector import CURRENT_OS, OS


class ConfigParsingException(Exception):
    pass


def __enum(table: dict[str, str | Any], key: str, enum: Any, default: int = 0) -> Any:
    if key not in table:
        return enum(default)
    v = table[key]
    if not isinstance(v, str):
        raise ConfigParsingException(f"'{key}' has value {v!r}. Expected a string.")
    stripped = v.strip()
    if stripped != "" and stripped.lstrip("+-").isdigit():
        try:
            return enum(int(stripped))
        except (ValueError, OverflowError) as exc:
            raise ConfigParsingException(
                f"Invalid value {v!r} for key '{key}'."
            ) from exc
    lowered = stripped.lower()
    for name in dir(enum):
        if name.startswith("_"):
            continue
        member = getattr(enum, name)
        if callable(member):
            continue
        if name.lower() == lowered:
            return member
    raise ConfigParsingException(f"Invalid value {v!r} for key '{key}'.")


def __str(table: dict[str, str | Any], key: str, default: str = "") -> str:
    v = table.get(key, default)
    if isinstance(v, str):
        return v
    raise ConfigParsingException(f"'{key}' has value {v!r}. Expected a string.")


def __opt_str(table: dict[str, str | Any], key: str) -> str | None:
    if key not in table:
        return None
    v = table[key]
    if isinstance(v, str):
        return v
    raise ConfigParsingException(f"'{key}' has value {v!r}. Expected a string.")


def __bool(table: dict[str, bool | Any], key: str, default: bool = False) -> bool:
    v = table.get(key, default)
    if isinstance(v, bool):
        return v
    raise ConfigParsingException(f"'{key}' has value {v!r}. Expected a bool.")


def __int(table: dict[str, int | Any], key: str, default: int = 0) -> int:
    v = table.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ConfigParsingException(f"'{key}' has value {v!r}. Expected an int.")
    if not 0 <= v <= 0xFFFFFFFF:
        raise ConfigParsingException(
            f"'{key}' has value {v!r}. Expected an unsigned 32-bit int."
        )
    return v


def __table(table: dict[str, dict[str, Any] | Any], key: str) -> dict[str, Any]:
    v = table.get(key, {})
    if isinstance(v, dict):
        return v  # type: ignore
    raise ConfigParsingException(f"'{key}' has value {v!r}. Expected a table.")


def __list(table: dict[str, list[Any] | Any], key: str) -> list[Any]:
    v = table.get(key, [])
    if isinstance(v, list):
        return v
    raise ConfigParsingException(f"'{key}' has value {v!r}. Expected an array.")


def __team(table: dict[str, Literal["blue", "orange", 0, 1] | Any]) -> int:
    if "team" not in table:
        return 0
    v = table["team"]
    if isinstance(v, bool):
        raise ConfigParsingException(
            f'\'team\' has value {v!r}. Expected a 0, 1, "blue", or "orange".'
        )
    if isinstance(v, str):
        if v.lower() == "blue":
            return 0
        if v.lower() == "orange":
            return 1
    elif isinstance(v, int):
        if 0 <= v <= 1:
            return v
    raise ConfigParsingException(
        f'\'team\' has value {v!r}. Expected a 0, 1, "blue", or "orange".'
    )


def __run_command(settings: dict[str, Any]) -> str:
    run_command = __str(settings, "run_command")
    if CURRENT_OS != OS.WINDOWS:
        run_command_linux = __str(settings, "run_command_linux")
        if run_command_linux != "":
            return run_command_linux
        # No Linux run command is set. Run the Windows command via Wine.
        if run_command != "":
            return f"wine {run_command}"
        return ""
    return run_command


__environment_pattern = re.compile(
    r"%([^%]+)%|\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))"
)


def __expand_environment(value: str) -> str:
    # Use one pass so variable references inside replacement values stay literal.
    return __environment_pattern.sub(
        lambda m: os.environ.get(m.group(1) or m.group(2) or m.group(3), m.group(0)),
        value,
    )


def __environment(settings: dict[str, Any]) -> list[flat.EnvironmentVariable]:
    env_table = __table(settings, "environment")
    values: dict[str, str] = {}

    for key, raw in env_table.items():
        if key == "windows" or key == "linux":
            continue
        if not isinstance(raw, str):
            raise ConfigParsingException(
                f"'{key}' has value {raw!r}. Expected a string."
            )
        values[key] = raw

    platform = (
        "windows"
        if CURRENT_OS == OS.WINDOWS
        else "linux"
        if CURRENT_OS == OS.LINUX
        else None
    )
    if platform is not None and platform in env_table:
        platform_table = env_table[platform]
        if not isinstance(platform_table, dict):
            raise ConfigParsingException(
                f"'{platform}' has value {platform_table!r}. Expected a table."
            )
        for key, raw in platform_table.items():
            if not isinstance(raw, str):
                raise ConfigParsingException(
                    f"'{key}' has value {raw!r}. Expected a string."
                )
            values[key] = __expand_environment(raw)

    return [flat.EnvironmentVariable(name=k, value=v) for k, v in values.items()]


def __abspath(path: Path | str) -> Path:
    # os.path.abspath normalizes ".." without resolving symlinks,
    # matching C# Path.GetFullPath.
    return Path(os.path.abspath(path))


def __match_loadout_override(
    car_table: dict[str, Any], match_dir: Path
) -> Path | str | None:
    raw = __opt_str(car_table, "loadout_file")
    if raw is None:
        return None
    if raw == "":
        # Empty string suppresses the loadout.
        return ""
    return match_dir / raw


def __auto_save_replay(match_table: dict[str, Any]) -> bool:
    # Both spellings are accepted. The plural C# reference key wins.
    if "auto_save_replays" in match_table:
        return __bool(match_table, "auto_save_replays")
    return __bool(match_table, "auto_save_replay")


def load_match_config(config_path: Path | str) -> flat.MatchConfiguration:
    """
    Reads the match toml file at the provided path and creates the corresponding MatchConfiguration.
    """
    config_path = __abspath(config_path)
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    rlbot_table = __table(config, "rlbot")
    match_table = __table(config, "match")
    mutator_table = __table(config, "mutators")

    players: list[flat.PlayerConfiguration] = []
    cars = __list(config, "cars")
    for i, car_table in enumerate(cars):
        if not isinstance(car_table, dict):
            raise ConfigParsingException(
                f"'cars[{i}]' has value {car_table!r}. Expected a table."
            )
        team = __team(car_table)
        variant = __str(car_table, "type", "rlbot").lower()
        name_override = __opt_str(car_table, "name")
        loadout_override = __match_loadout_override(car_table, config_path.parent)

        if variant == "human":
            players.append(get_human(team))
            continue

        car_config = __str(car_table, "config_file")

        if car_config != "":
            abs_config_path = __abspath(config_path.parent / car_config)
            if variant == "rlbot":
                auto_start = __bool(car_table, "auto_start", True)
                players.append(
                    load_player_config(
                        abs_config_path,
                        team,
                        name_override,
                        loadout_override,
                        auto_start,
                    )
                )
            elif variant == "psyonix":
                # Skill comes from the linked toml file. The passed
                # skill is only a fallback and is not used here.
                players.append(
                    load_psyonix_config(
                        team,
                        flat.PsyonixSkill.AllStar,
                        name_override,
                        loadout_override,
                        abs_config_path,
                    )
                )
            else:
                raise ConfigParsingException(
                    f"Invalid player type {variant!r} for player {len(players)}."
                )
        else:
            if variant == "psyonix":
                skill = __enum(
                    car_table,
                    "skill",
                    flat.PsyonixSkill,
                    int(flat.PsyonixSkill.AllStar),
                )
                players.append(
                    __unlinked_psyonix(team, skill, name_override, loadout_override)
                )
            elif variant == "rlbot":
                raise ConfigParsingException(
                    f"'cars[{i}].config_file' is empty. "
                    + "Custom bots must specify a config file."
                )
            else:
                raise ConfigParsingException(
                    f"Invalid player type {variant!r} for player {len(players)}."
                )

    scripts: list[flat.ScriptConfiguration] = []
    scripts_list = __list(config, "scripts")
    for i, script_table in enumerate(scripts_list):
        if not isinstance(script_table, dict):
            raise ConfigParsingException(
                f"'scripts[{i}]' has value {script_table!r}. Expected a table."
            )
        script_config = __str(script_table, "config_file")
        if script_config == "":
            raise ConfigParsingException(
                f"'scripts[{i}].config_file' is empty. Scripts must specify a config file."
            )
        abs_config_path = __abspath(config_path.parent / script_config)
        auto_start = __bool(script_table, "auto_start", True)
        scripts.append(load_script_config(abs_config_path, auto_start))

    mutators = flat.MutatorSettings(
        match_length=__enum(
            mutator_table,
            "match_length",
            flat.MatchLengthMutator,
            int(flat.MatchLengthMutator.FiveMinutes),
        ),
        max_score=__enum(
            mutator_table,
            "max_score",
            flat.MaxScoreMutator,
            int(flat.MaxScoreMutator.Unlimited),
        ),
        multi_ball=__enum(
            mutator_table,
            "multi_ball",
            flat.MultiBallMutator,
            int(flat.MultiBallMutator.One),
        ),
        overtime=__enum(
            mutator_table,
            "overtime",
            flat.OvertimeMutator,
            int(flat.OvertimeMutator.Unlimited),
        ),
        series_length=__enum(
            mutator_table,
            "series_length",
            flat.SeriesLengthMutator,
            int(flat.SeriesLengthMutator.Unlimited),
        ),
        game_speed=__enum(
            mutator_table,
            "game_speed",
            flat.GameSpeedMutator,
            int(flat.GameSpeedMutator.Default),
        ),
        ball_max_speed=__enum(
            mutator_table,
            "ball_max_speed",
            flat.BallMaxSpeedMutator,
            int(flat.BallMaxSpeedMutator.Default),
        ),
        ball_type=__enum(
            mutator_table,
            "ball_type",
            flat.BallTypeMutator,
            int(flat.BallTypeMutator.Default),
        ),
        ball_weight=__enum(
            mutator_table,
            "ball_weight",
            flat.BallWeightMutator,
            int(flat.BallWeightMutator.Default),
        ),
        ball_size=__enum(
            mutator_table,
            "ball_size",
            flat.BallSizeMutator,
            int(flat.BallSizeMutator.Default),
        ),
        ball_bounciness=__enum(
            mutator_table,
            "ball_bounciness",
            flat.BallBouncinessMutator,
            int(flat.BallBouncinessMutator.Default),
        ),
        boost_amount=__enum(
            mutator_table,
            "boost_amount",
            flat.BoostAmountMutator,
            int(flat.BoostAmountMutator.NormalBoost),
        ),
        rumble=__enum(
            mutator_table,
            "rumble",
            flat.RumbleMutator,
            int(flat.RumbleMutator.Off),
        ),
        boost_strength=__enum(
            mutator_table,
            "boost_strength",
            flat.BoostStrengthMutator,
            int(flat.BoostStrengthMutator.One),
        ),
        gravity=__enum(
            mutator_table,
            "gravity",
            flat.GravityMutator,
            int(flat.GravityMutator.Default),
        ),
        demolish=__enum(
            mutator_table,
            "demolish",
            flat.DemolishMutator,
            int(flat.DemolishMutator.Default),
        ),
        respawn_time=__enum(
            mutator_table,
            "respawn_time",
            flat.RespawnTimeMutator,
            int(flat.RespawnTimeMutator.ThreeSeconds),
        ),
        max_time=__enum(
            mutator_table,
            "max_time",
            flat.MaxTimeMutator,
            int(flat.MaxTimeMutator.Unlimited),
        ),
        game_event=__enum(
            mutator_table,
            "game_event",
            flat.GameEventMutator,
            int(flat.GameEventMutator.Default),
        ),
        audio=__enum(
            mutator_table,
            "audio",
            flat.AudioMutator,
            int(flat.AudioMutator.Default),
        ),
        ball_gravity=__enum(
            mutator_table,
            "ball_gravity",
            flat.BallGravityMutator,
            int(flat.BallGravityMutator.Default),
        ),
        territory=__enum(
            mutator_table,
            "territory",
            flat.TerritoryMutator,
            int(flat.TerritoryMutator.Off),
        ),
        stale_ball=__enum(
            mutator_table,
            "stale_ball",
            flat.StaleBallMutator,
            int(flat.StaleBallMutator.Unlimited),
        ),
        jump=__enum(
            mutator_table,
            "jump",
            flat.JumpMutator,
            int(flat.JumpMutator.Default),
        ),
        dodge_timer=__enum(
            mutator_table,
            "dodge_timer",
            flat.DodgeTimerMutator,
            int(flat.DodgeTimerMutator.OnePointTwentyFiveSeconds),
        ),
        possession_score=__enum(
            mutator_table,
            "possession_score",
            flat.PossessionScoreMutator,
            int(flat.PossessionScoreMutator.Off),
        ),
        demolish_score=__enum(
            mutator_table,
            "demolish_score",
            flat.DemolishScoreMutator,
            int(flat.DemolishScoreMutator.Zero),
        ),
        normal_goal_score=__enum(
            mutator_table,
            "normal_goal_score",
            flat.NormalGoalScoreMutator,
            int(flat.NormalGoalScoreMutator.One),
        ),
        aerial_goal_score=__enum(
            mutator_table,
            "aerial_goal_score",
            flat.AerialGoalScoreMutator,
            int(flat.AerialGoalScoreMutator.One),
        ),
        assist_goal_score=__enum(
            mutator_table,
            "assist_goal_score",
            flat.AssistGoalScoreMutator,
            int(flat.AssistGoalScoreMutator.Zero),
        ),
        input_restriction=__enum(
            mutator_table,
            "input_restriction",
            flat.InputRestrictionMutator,
            int(flat.InputRestrictionMutator.Default),
        ),
    )

    # "soccer" is an alias of "Soccar".
    game_mode_table = dict(match_table)
    game_mode_raw = game_mode_table.get("game_mode")
    if isinstance(game_mode_raw, str) and game_mode_raw.lower() == "soccer":
        game_mode_table["game_mode"] = "Soccar"
    game_mode = __enum(
        game_mode_table, "game_mode", flat.GameMode, int(flat.GameMode.Soccar)
    )

    if "enable_rendering" in match_table:
        raw_rendering = match_table["enable_rendering"]
        if isinstance(raw_rendering, bool):
            enable_rendering = (
                flat.DebugRendering.OnByDefault
                if raw_rendering
                else flat.DebugRendering.AlwaysOff
            )
        else:
            enable_rendering = __enum(
                match_table,
                "enable_rendering",
                flat.DebugRendering,
                int(flat.DebugRendering.OffByDefault),
            )
    else:
        enable_rendering = flat.DebugRendering.OffByDefault

    return flat.MatchConfiguration(
        launcher=__enum(
            rlbot_table, "launcher", flat.Launcher, int(flat.Launcher.Steam)
        ),
        launcher_arg=__str(rlbot_table, "launcher_arg"),
        auto_start_agents=__bool(rlbot_table, "auto_start_agents", True),
        wait_for_agents=__bool(rlbot_table, "wait_for_agents", True),
        performance_monitor=__enum(
            rlbot_table,
            "performance_monitor",
            flat.PerformanceMonitor,
            int(flat.PerformanceMonitor.ShowWhenSuboptimal),
        ),
        game_map_upk=__str(match_table, "game_map_upk", "Stadium_P"),
        player_configurations=players,
        script_configurations=scripts,
        game_mode=game_mode,
        skip_replays=__bool(match_table, "skip_replays"),
        instant_start=__bool(match_table, "start_without_countdown"),
        mutators=mutators,
        existing_match_behavior=__enum(
            match_table,
            "existing_match_behavior",
            flat.ExistingMatchBehavior,
            int(flat.ExistingMatchBehavior.Restart),
        ),
        enable_rendering=enable_rendering,
        enable_state_setting=__bool(match_table, "enable_state_setting", True),
        auto_save_replay=__auto_save_replay(match_table),
        freeplay=__bool(match_table, "freeplay"),
    )


def __unlinked_psyonix(
    team: int,
    skill: flat.PsyonixSkill,
    name_override: str | None,
    loadout_override: Path | str | None,
) -> flat.PlayerConfiguration:
    if loadout_override is None or loadout_override == "":
        loadout = None
    else:
        loadout = load_player_loadout(loadout_override, team)
    return flat.PlayerConfiguration(
        flat.PsyonixBot(
            name_override if name_override is not None else "",
            loadout,
            skill,
        ),
        team,
        0,
    )


def load_player_loadout(path: Path | str, team: int) -> flat.PlayerLoadout:
    """
    Reads the loadout TOML for the blue team (0) or the orange team (1).
    """
    if not isinstance(team, int) or isinstance(team, bool) or team not in (0, 1):
        raise ConfigParsingException(
            f"Invalid team {team!r}. Use 0 (blue) or 1 (orange)."
        )

    path = __abspath(path)
    with open(path, "rb") as f:
        config = tomllib.load(f)

    table_name = "blue_loadout" if team == 0 else "orange_loadout"
    loadout = __table(config, table_name)
    paint_table = __table(loadout, "paint")
    paint = flat.LoadoutPaint(
        car_paint_id=__int(paint_table, "car_paint_id"),
        decal_paint_id=__int(paint_table, "decal_paint_id"),
        wheels_paint_id=__int(paint_table, "wheels_paint_id"),
        boost_paint_id=__int(paint_table, "boost_paint_id"),
        antenna_paint_id=__int(paint_table, "antenna_paint_id"),
        hat_paint_id=__int(paint_table, "hat_paint_id"),
        trails_paint_id=__int(paint_table, "trails_paint_id"),
        goal_explosion_paint_id=__int(paint_table, "goal_explosion_paint_id"),
    )

    return flat.PlayerLoadout(
        team_color_id=__int(loadout, "team_color_id"),
        custom_color_id=__int(loadout, "custom_color_id"),
        car_id=__int(loadout, "car_id"),
        decal_id=__int(loadout, "decal_id"),
        wheels_id=__int(loadout, "wheels_id"),
        boost_id=__int(loadout, "boost_id"),
        antenna_id=__int(loadout, "antenna_id"),
        hat_id=__int(loadout, "hat_id"),
        paint_finish_id=__int(loadout, "paint_finish_id"),
        custom_finish_id=__int(loadout, "custom_finish_id"),
        engine_audio_id=__int(loadout, "engine_audio_id"),
        trails_id=__int(loadout, "trails_id"),
        goal_explosion_id=__int(loadout, "goal_explosion_id"),
        loadout_paint=paint,
    )


def load_player_config(
    path: Path | str,
    team: int,
    name_override: str | None = None,
    loadout_override: Path | str | None = None,
    auto_start: bool = True,
) -> flat.PlayerConfiguration:
    """
    Reads the bot toml file at the provided path and
    creates a `PlayerConfiguration` of the given type for the given team.
    """
    path = __abspath(path)
    with open(path, "rb") as f:
        config = tomllib.load(f)

    settings = __table(config, "settings")

    root_dir = path.parent
    if "root_dir" in settings:
        root_dir /= Path(__str(settings, "root_dir"))

    run_command = __run_command(settings) if auto_start else ""

    if loadout_override is None:
        settings_loadout = __opt_str(settings, "loadout_file")
        if settings_loadout is None or settings_loadout == "":
            loadout_path = None
        else:
            loadout_path = path.parent / settings_loadout
    elif loadout_override == "":
        # Empty string suppresses the loadout.
        loadout_path = None
    else:
        loadout_path = loadout_override
    loadout = (
        load_player_loadout(loadout_path, team) if loadout_path is not None else None
    )

    return flat.PlayerConfiguration(
        flat.CustomBot(
            name_override if name_override is not None else __str(settings, "name"),
            str(root_dir),
            run_command,
            loadout,
            __str(settings, "agent_id"),
            __bool(settings, "hivemind"),
            environment=__environment(settings),
        ),
        team,
        0,
    )


def load_psyonix_config(
    team: int,
    skill_level: flat.PsyonixSkill,
    name_override: str | None = None,
    loadout_override: Path | str | None = None,
    path: Path | str | None = None,
) -> flat.PlayerConfiguration:
    """
    Creates a `PlayerConfiguration` for a Psyonix bot of the given team and skill.
    If a path is provided, the skill is read from the linked toml file,
    which also supplies the default name and loadout unless overridden here.
    Without a path, `skill_level` is used directly.
    """
    if path is None:
        name = name_override
        if loadout_override is None or loadout_override == "":
            loadout_path = None
        else:
            loadout_path = loadout_override
    else:
        path = __abspath(path)
        with open(path, "rb") as f:
            config = tomllib.load(f)

        skill_level = __enum(
            config, "skill", flat.PsyonixSkill, int(flat.PsyonixSkill.AllStar)
        )
        settings = __table(config, "settings")

        name = name_override if name_override is not None else __str(settings, "name")

        if loadout_override is None:
            settings_loadout = __opt_str(settings, "loadout_file")
            if settings_loadout is None or settings_loadout == "":
                loadout_path = None
            else:
                loadout_path = path.parent / settings_loadout
        elif loadout_override == "":
            # Empty string suppresses the loadout.
            loadout_path = None
        else:
            loadout_path = loadout_override

    loadout = (
        load_player_loadout(loadout_path, team) if loadout_path is not None else None
    )

    return flat.PlayerConfiguration(
        flat.PsyonixBot(
            name if name is not None else "",
            loadout,
            skill_level,
        ),
        team,
        0,
    )


def get_human(team: int) -> flat.PlayerConfiguration:
    """
    Creates a `PlayerConfiguration` for a human player on the given team.
    """
    return flat.PlayerConfiguration(flat.Human(), team)


def load_script_config(
    path: Path | str, auto_start: bool = True
) -> flat.ScriptConfiguration:
    """
    Reads the script toml file at the provided path and creates a `ScriptConfiguration` from it.
    """
    path = __abspath(path)
    with open(path, "rb") as f:
        config = tomllib.load(f)

    settings = __table(config, "settings")

    root_dir = path.parent
    if "root_dir" in settings:
        root_dir /= Path(__str(settings, "root_dir"))

    run_command = __run_command(settings)
    if not auto_start:
        run_command = ""

    return flat.ScriptConfiguration(
        __str(settings, "name"),
        str(root_dir),
        run_command,
        0,
        __str(settings, "agent_id"),
        environment=__environment(settings),
    )
