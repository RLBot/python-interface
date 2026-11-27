"""Regression tests for match parser parity with core.

Use only file operations and the parser API.
Run with: pytest tests/test_config_parity.py -v
"""

from collections.abc import Sequence
from pathlib import Path

import pytest

import rlbot.config as config_mod
from rlbot import flat
from rlbot.config import (
    ConfigParsingException,
    load_match_config,
    load_player_config,
    load_player_loadout,
    load_psyonix_config,
    load_script_config,
)
from rlbot.utils.os_detector import OS

DIR = Path(__file__).parent


def write(path: Path, text: str) -> Path:
    """Write text to path. Create parent folders as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def make_bot(tmp: Path, name: str = "bot.toml", with_loadout: bool = True) -> Path:
    """Create a minimal bot file. Return its path."""
    lines = [
        "[settings]",
        'agent_id = "test/bot"',
        'name = "Test Bot"',
        'run_command = "python bot.py"',
        'run_command_linux = "python3 bot.py"',
    ]
    if with_loadout:
        lines.append('loadout_file = "loadout.toml"')
        write(
            tmp / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 1\n[orange_loadout]\nteam_color_id = 2\n",
        )
    write(tmp / name, "\n".join(lines) + "\n")
    return tmp / name


def make_script(tmp: Path, name: str = "script.toml") -> Path:
    """Create a minimal script file. Return its path."""
    write(
        tmp / name,
        "[settings]\n"
        'agent_id = "test/script"\n'
        'name = "Test Script"\n'
        'run_command = "python script.py"\n'
        'run_command_linux = "python3 script.py"\n',
    )
    return tmp / name


def make_linked(tmp: Path) -> Path:
    """Create a linked bot file and its loadout. Return the bot path."""
    write(
        tmp / "linked.toml",
        "[settings]\n"
        'agent_id = "test/linked"\n'
        'name = "Linked Name"\n'
        'run_command = "python bot.py"\n'
        'loadout_file = "loadout.toml"\n',
    )
    write(
        tmp / "loadout.toml",
        "[blue_loadout]\nteam_color_id = 33\n[orange_loadout]\nteam_color_id = 34\n",
    )
    return tmp / "linked.toml"


def _mutators(m: flat.MatchConfiguration) -> flat.MutatorSettings:
    """Return mutators. Fail if missing."""
    mut = m.mutators
    assert mut is not None
    return mut


def _custom(variety: flat.CustomBot | flat.Human | flat.PsyonixBot) -> flat.CustomBot:
    """Return custom bot variety. Fail if wrong type."""
    assert isinstance(variety, flat.CustomBot)
    return variety


def _psyonix(variety: flat.CustomBot | flat.Human | flat.PsyonixBot) -> flat.PsyonixBot:
    """Return Psyonix bot variety. Fail if wrong type."""
    assert isinstance(variety, flat.PsyonixBot)
    return variety


def _custom_env(
    variety: flat.CustomBot | flat.Human | flat.PsyonixBot,
) -> Sequence[flat.EnvironmentVariable]:
    """Return bot environment list. Fail if missing."""
    bot = _custom(variety)
    assert bot.environment is not None
    return bot.environment


def _script_env(cfg: flat.ScriptConfiguration) -> Sequence[flat.EnvironmentVariable]:
    """Return script environment list. Fail if missing."""
    assert cfg.environment is not None
    return cfg.environment


def _loadout(loadout: flat.PlayerLoadout | None) -> flat.PlayerLoadout:
    """Return loadout. Fail if missing."""
    assert loadout is not None
    return loadout


class TestMatchDefaultsKeysRendering:
    """Check match defaults and key names."""

    def test_empty_file_uses_documented_defaults(self, tmp_path: Path):
        p = write(tmp_path / "empty.toml", "")
        m = load_match_config(p)
        assert m.launcher == flat.Launcher.Steam
        assert m.launcher_arg == ""
        assert m.auto_start_agents
        assert m.wait_for_agents
        assert m.game_map_upk == "Stadium_P"
        assert m.game_mode == flat.GameMode.Soccar
        assert not m.skip_replays
        assert not m.instant_start
        assert m.existing_match_behavior == flat.ExistingMatchBehavior.Restart
        assert m.enable_rendering == flat.DebugRendering.OffByDefault
        assert m.enable_state_setting
        assert not m.auto_save_replay
        assert not m.freeplay
        assert m.performance_monitor == flat.PerformanceMonitor.ShowWhenSuboptimal
        assert m.player_configurations == []
        assert m.script_configurations == []

    def test_start_without_countdown_key_maps_to_instant_start(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            "[match]\nstart_without_countdown = true\n",
        )
        m = load_match_config(p)
        assert m.instant_start

    def test_soccer_alias_maps_to_soccar(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", '[match]\ngame_mode = "soccer"\n')
        m = load_match_config(p)
        assert m.game_mode == flat.GameMode.Soccar

    def test_rendering_false_maps_to_always_off(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[match]\nenable_rendering = false\n")
        m = load_match_config(p)
        assert m.enable_rendering == flat.DebugRendering.AlwaysOff

    def test_rendering_true_maps_to_on_by_default(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[match]\nenable_rendering = true\n")
        m = load_match_config(p)
        assert m.enable_rendering == flat.DebugRendering.OnByDefault

    def test_rendering_string_off_by_default(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[match]\nenable_rendering = "OffByDefault"\n',
        )
        m = load_match_config(p)
        assert m.enable_rendering == flat.DebugRendering.OffByDefault

    def test_rendering_string_always_off(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[match]\nenable_rendering = "AlwaysOff"\n',
        )
        m = load_match_config(p)
        assert m.enable_rendering == flat.DebugRendering.AlwaysOff

    def test_launcher_arg_and_freeplay_and_autosave(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[rlbot]\nlauncher = "Steam"\nlauncher_arg = "legendary"\n'
            "[match]\nfreeplay = true\nauto_save_replay = true\n",
        )
        m = load_match_config(p)
        assert m.launcher_arg == "legendary"
        assert m.freeplay
        assert m.auto_save_replay

    def test_plural_auto_save_replays_enables_saving(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[match]\nauto_save_replays = true\n")
        m = load_match_config(p)
        assert m.auto_save_replay

    def test_plural_auto_save_replays_wins_over_singular(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            "[match]\nauto_save_replay = true\nauto_save_replays = false\n",
        )
        m = load_match_config(p)
        assert not m.auto_save_replay


class TestMutatorParity:
    """Check all mutators from core are parsed."""

    def test_extended_mutators(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            "[mutators]\n"
            'ball_gravity = "High"\n'
            'territory = "Territory"\n'
            'stale_ball = "ThirtySeconds"\n'
            'jump = "NoJumps"\n'
            'dodge_timer = "ThreeSeconds"\n'
            'possession_score = "ThreeSeconds"\n'
            'demolish_score = "Three"\n'
            'normal_goal_score = "Five"\n'
            'aerial_goal_score = "Ten"\n'
            'assist_goal_score = "Three"\n'
            'input_restriction = "Backwards"\n',
        )
        m = load_match_config(p)
        mut = _mutators(m)
        assert mut.ball_gravity == flat.BallGravityMutator.High
        assert mut.territory == flat.TerritoryMutator.Territory
        assert mut.stale_ball == flat.StaleBallMutator.ThirtySeconds
        assert mut.jump == flat.JumpMutator.NoJumps
        assert mut.dodge_timer == flat.DodgeTimerMutator.ThreeSeconds
        assert mut.possession_score == flat.PossessionScoreMutator.ThreeSeconds
        assert mut.demolish_score == flat.DemolishScoreMutator.Three
        assert mut.normal_goal_score == flat.NormalGoalScoreMutator.Five
        assert mut.aerial_goal_score == flat.AerialGoalScoreMutator.Ten
        assert mut.assist_goal_score == flat.AssistGoalScoreMutator.Three
        assert mut.input_restriction == flat.InputRestrictionMutator.Backwards

    def test_core_mutators_case_insensitive(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[mutators]\nmatch_length = "TenMinutes"\ngravity = "rEvErsE"\n',
        )
        m = load_match_config(p)
        mut = _mutators(m)
        assert mut.match_length == flat.MatchLengthMutator.TenMinutes
        assert mut.gravity == flat.GravityMutator.Reverse

    def test_mutator_defaults_match_core(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "")
        m = load_match_config(p)
        mut = _mutators(m)
        assert mut.match_length == flat.MatchLengthMutator.FiveMinutes
        assert mut.max_score == flat.MaxScoreMutator.Unlimited
        assert mut.boost_amount == flat.BoostAmountMutator.NormalBoost
        assert mut.rumble == flat.RumbleMutator.Off
        assert mut.gravity == flat.GravityMutator.Default
        assert mut.respawn_time == flat.RespawnTimeMutator.ThreeSeconds
        assert mut.ball_gravity == flat.BallGravityMutator.Default
        assert mut.territory == flat.TerritoryMutator.Off


class TestAutoStart:
    """Check per-agent auto_start handling."""

    def test_car_auto_start_false_clears_run_command(self, tmp_path: Path):
        make_bot(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bot.toml"\nteam = 0\nauto_start = false\n',
        )
        m = load_match_config(p)
        variety = m.player_configurations[0].variety
        assert isinstance(variety, flat.CustomBot)
        assert _custom(variety).run_command == ""

    def test_car_auto_start_true_keeps_run_command(self, tmp_path: Path):
        make_bot(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bot.toml"\nteam = 0\nauto_start = true\n',
        )
        m = load_match_config(p)
        variety = m.player_configurations[0].variety
        assert _custom(variety).run_command != ""

    def test_script_auto_start_false_clears_run_command(self, tmp_path: Path):
        make_script(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[scripts]]\nconfig_file = "script.toml"\nauto_start = false\n',
        )
        m = load_match_config(p)
        assert m.script_configurations[0].run_command == ""

    def test_disabled_custom_bot_bad_run_command_type_loads_empty(self, tmp_path: Path):
        write(
            tmp_path / "bot.toml",
            '[settings]\nagent_id = "test/bot"\nname = "Test Bot"\nrun_command = 123\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0, auto_start=False)
        assert _custom(cfg.variety).run_command == ""


class TestWineFallback:
    """Check Linux run command fallback through Wine."""

    def test_linux_command_preferred_when_present(self, tmp_path: Path):
        bot = make_bot(tmp_path)
        cfg = load_player_config(bot, 0)
        # atba-style bot has run_command_linux set, so Linux build uses it.
        # Our helper sets run_command_linux to python3.
        assert "python3" in _custom(cfg.variety).run_command

    def test_wine_fallback_when_linux_command_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Wine Bot"\n'
            'run_command = "bot.exe"\n',
        )
        bot = tmp_path / "bot.toml"
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        cfg = load_player_config(bot, 0)
        assert _custom(cfg.variety).run_command == "wine bot.exe"

    def test_script_wine_fallback_when_linux_command_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        write(
            tmp_path / "script.toml",
            "[settings]\n"
            'agent_id = "test/script"\n'
            'name = "Wine Script"\n'
            'run_command = "run.exe"\n',
        )
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        cfg = load_script_config(tmp_path / "script.toml")
        assert cfg.run_command == "wine run.exe"


class TestEnvironment:
    """Check environment tables."""

    def test_common_values_remain_literal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("RLBOT_TEST_COMMON", "expanded-value")
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            'LITERAL = "$RLBOT_TEST_COMMON/x"\n'
            'BRACED = "${RLBOT_TEST_COMMON}/y"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("LITERAL") == "$RLBOT_TEST_COMMON/x"
        assert values.get("BRACED") == "${RLBOT_TEST_COMMON}/y"

    def test_linux_values_expand_and_override_common(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("RLBOT_TEST_EXPAND", "expanded-value")
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            'BOT_ENV = "bot-value"\n'
            'SHARED_ENV = "common"\n'
            "[settings.environment.linux]\n"
            'SHARED_ENV = "$RLBOT_TEST_EXPAND"\n'
            'PLATFORM_ENV = "$RLBOT_TEST_EXPAND/x"\n'
            'BRACED_ENV = "${RLBOT_TEST_EXPAND}/y"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("BOT_ENV") == "bot-value"
        assert values.get("SHARED_ENV") == "expanded-value"
        assert values.get("PLATFORM_ENV") == "expanded-value/x"
        assert values.get("BRACED_ENV") == "expanded-value/y"

    def test_inactive_platform_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            'SHARED_ENV = "common"\n'
            "[settings.environment.windows]\n"
            'SHARED_ENV = "windows-value"\n'
            'WIN_ONLY = "win"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("SHARED_ENV") == "common"
        assert "WIN_ONLY" not in values

    def test_unknown_vars_remain_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment.linux]\n"
            'UNKNOWN = "$RLBOT_DEFINITELY_MISSING_XYZ/x"\n'
            'BRACED = "${RLBOT_DEFINITELY_MISSING_XYZ}/y"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("UNKNOWN") == "$RLBOT_DEFINITELY_MISSING_XYZ/x"
        assert values.get("BRACED") == "${RLBOT_DEFINITELY_MISSING_XYZ}/y"

    def test_windows_values_expand_percent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("RLBOT_TEST_WIN", "win-value")
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.WINDOWS)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            'COMMON = "common"\n'
            "[settings.environment.windows]\n"
            'SHARED = "%RLBOT_TEST_WIN%"\n'
            'WIN_ONLY = "%RLBOT_TEST_WIN%/x"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("COMMON") == "common"
        assert values.get("SHARED") == "win-value"
        assert values.get("WIN_ONLY") == "win-value/x"

    def test_linux_cross_syntax_percent_and_dollar_expand(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("RLBOT_TEST_CROSS", "cross-value")
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment.linux]\n"
            'PCT = "%RLBOT_TEST_CROSS%/x"\n'
            'DOLLAR = "$RLBOT_TEST_CROSS/x"\n'
            'BRACED = "${RLBOT_TEST_CROSS}/y"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("PCT") == "cross-value/x"
        assert values.get("DOLLAR") == "cross-value/x"
        assert values.get("BRACED") == "cross-value/y"

    def test_platform_expansion_does_not_rescan_replacements(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        monkeypatch.setenv("RLBOT_OUTER", "$RLBOT_INNER")
        monkeypatch.setenv("RLBOT_INNER", "value")
        monkeypatch.setenv("RLBOT_TEST_DIR(X86)", "test-dir")
        path = write(
            tmp_path / "bot.toml",
            "[settings.environment.linux]\n"
            'VALUE = "%RLBOT_OUTER%|$RLBOT_INNER|%RLBOT_TEST_DIR(X86)%"\n',
        )
        bot = load_player_config(path, 0).variety
        assert {e.name: e.value for e in _custom_env(bot)} == {
            "VALUE": "$RLBOT_INNER|value|test-dir"
        }

    def test_inactive_linux_values_stay_absent_and_common_stays_literal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.WINDOWS)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            'SHARED = "common"\n'
            'LITERAL = "$SHOULD_STAY_LITERAL/x"\n'
            "[settings.environment.linux]\n"
            'SHARED = "linux-value"\n'
            'LINUX_ONLY = "linux"\n',
        )
        cfg = load_player_config(tmp_path / "bot.toml", 0)
        values = {e.name: e.value for e in _custom_env(cfg.variety)}
        assert values.get("SHARED") == "common"
        assert values.get("LITERAL") == "$SHOULD_STAY_LITERAL/x"
        assert "LINUX_ONLY" not in values

    def test_script_environment_transports_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("RLBOT_TEST_SCRIPT", "expanded-value")
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "script.toml",
            "[settings]\n"
            'agent_id = "test/script"\n'
            'name = "Env Script"\n'
            'run_command = "python script.py"\n'
            "[settings.environment]\n"
            'SCRIPT_ENV = "script-value"\n'
            "[settings.environment.linux]\n"
            'LINUX_ENV = "$RLBOT_TEST_SCRIPT/x"\n',
        )
        cfg = load_script_config(tmp_path / "script.toml")
        values = {e.name: e.value for e in _script_env(cfg)}
        assert values.get("SCRIPT_ENV") == "script-value"
        assert values.get("LINUX_ENV") == "expanded-value/x"

    def test_non_string_common_environment_raises(self, tmp_path: Path):
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment]\n"
            "NUM = 123\n",
        )
        with pytest.raises(ConfigParsingException):
            load_player_config(tmp_path / "bot.toml", 0)

    def test_non_string_platform_environment_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(config_mod, "CURRENT_OS", OS.LINUX)
        write(
            tmp_path / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Env Bot"\n'
            'run_command = "python bot.py"\n'
            "[settings.environment.linux]\n"
            "NUM = 123\n",
        )
        with pytest.raises(ConfigParsingException):
            load_player_config(tmp_path / "bot.toml", 0)


class TestLoadoutOverrideAndPathAnchoring:
    """Check loadout override rules and path anchoring."""

    def test_empty_override_suppresses_loadout(self, tmp_path: Path):
        make_bot(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bot.toml"\nteam = 0\nloadout_file = ""\n',
        )
        m = load_match_config(p)
        variety = m.player_configurations[0].variety
        assert _custom(variety).loadout is None

    def test_override_anchored_at_match_dir(self, tmp_path: Path):
        bot_dir = tmp_path / "bots"
        bot_dir.mkdir()
        write(
            bot_dir / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Bot"\n'
            'run_command = "python bot.py"\n'
            'loadout_file = "bot_loadout.toml"\n',
        )
        write(
            bot_dir / "bot_loadout.toml",
            "[blue_loadout]\nteam_color_id = 11\n"
            "[orange_loadout]\nteam_color_id = 12\n",
        )
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        write(
            override_dir / "override.toml",
            "[blue_loadout]\nteam_color_id = 99\n"
            "[orange_loadout]\nteam_color_id = 100\n",
        )
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bots/bot.toml"\n'
            'team = 0\nloadout_file = "overrides/override.toml"\n',
        )
        m = load_match_config(p)
        assert (
            _loadout(_custom(m.player_configurations[0].variety).loadout).team_color_id
            == 99
        )

    def test_bot_relative_loadout_anchored_at_bot_dir(self, tmp_path: Path):
        bot_dir = tmp_path / "deep" / "bots"
        bot_dir.mkdir(parents=True)
        write(
            bot_dir / "bot.toml",
            "[settings]\n"
            'agent_id = "test/bot"\n'
            'name = "Bot"\n'
            'run_command = "python bot.py"\n'
            'loadout_file = "loadout.toml"\n',
        )
        write(
            bot_dir / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 21\n"
            "[orange_loadout]\nteam_color_id = 22\n",
        )
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "deep/bots/bot.toml"\nteam = 0\n',
        )
        m = load_match_config(p)
        assert (
            _loadout(_custom(m.player_configurations[0].variety).loadout).team_color_id
            == 21
        )


class TestPsyonixLinkedValues:
    """Check Psyonix bots with linked config files."""

    def test_psyonix_inherits_name_and_loadout(self, tmp_path: Path):
        make_linked(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "linked.toml"\nteam = 0\ntype = "Psyonix"\n',
        )
        m = load_match_config(p)
        variety = m.player_configurations[0].variety
        assert isinstance(variety, flat.PsyonixBot)
        bot = _psyonix(variety)
        assert bot.name == "Linked Name"
        assert bot.loadout is not None
        assert _loadout(bot.loadout).team_color_id == 33

    def test_psyonix_explicit_name_wins(self, tmp_path: Path):
        make_linked(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "linked.toml"\nteam = 0\n'
            'type = "Psyonix"\nname = "Override"\n',
        )
        m = load_match_config(p)
        assert _psyonix(m.player_configurations[0].variety).name == "Override"

    def test_psyonix_explicit_loadout_wins(self, tmp_path: Path):
        make_linked(tmp_path)
        write(
            tmp_path / "other.toml",
            "[blue_loadout]\nteam_color_id = 77\n"
            "[orange_loadout]\nteam_color_id = 78\n",
        )
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "linked.toml"\nteam = 0\n'
            'type = "Psyonix"\nloadout_file = "other.toml"\n',
        )
        m = load_match_config(p)
        assert (
            _loadout(_psyonix(m.player_configurations[0].variety).loadout).team_color_id
            == 77
        )

    def test_psyonix_skill_from_car_table(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nteam = 0\ntype = "Psyonix"\nskill = "Pro"\n',
        )
        m = load_match_config(p)
        assert (
            _psyonix(m.player_configurations[0].variety).bot_skill
            == flat.PsyonixSkill.Pro
        )

    @pytest.mark.parametrize("car_fields", ["", 'type = "RLBot"\nconfig_file = ""\n'])
    def test_rlbot_without_config_uses_psyonix(self, tmp_path: Path, car_fields: str):
        write(tmp_path / "loadout.toml", "[orange_loadout]\ncar_id = 23\n")
        path = write(
            tmp_path / "m.toml",
            f"[[cars]]\n{car_fields}"
            'team = "Orange"\nskill = "Pro"\nname = "Boomer"\n'
            'loadout_file = "loadout.toml"\n',
        )
        car = load_match_config(path).player_configurations[0]
        bot = _psyonix(car.variety)
        assert car.team == 1
        assert bot.name == "Boomer"
        assert bot.bot_skill == flat.PsyonixSkill.Pro
        assert _loadout(bot.loadout).car_id == 23

    def test_psyonix_default_skill_is_allstar(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", '[[cars]]\nteam = 1\ntype = "Psyonix"\n')
        m = load_match_config(p)
        assert (
            _psyonix(m.player_configurations[0].variety).bot_skill
            == flat.PsyonixSkill.AllStar
        )

    def test_direct_psyonix_helper_inherits_linked_values(self, tmp_path: Path):
        linked = make_linked(tmp_path)
        cfg = load_psyonix_config(0, flat.PsyonixSkill.Pro, None, None, linked)
        bot = _psyonix(cfg.variety)
        assert bot.name == "Linked Name"
        assert _loadout(bot.loadout).team_color_id == 33

    def test_psyonix_skill_from_linked_root_wins_over_overrides(self, tmp_path: Path):
        write(
            tmp_path / "linked.toml",
            'skill = "Pro"\n'
            "[settings]\n"
            'agent_id = "test/linked"\n'
            'name = "Linked Name"\n'
            'run_command = "python bot.py"\n'
            'loadout_file = "loadout.toml"\n',
        )
        write(
            tmp_path / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 33\n"
            "[orange_loadout]\nteam_color_id = 34\n",
        )
        write(
            tmp_path / "other.toml",
            "[blue_loadout]\nteam_color_id = 77\n"
            "[orange_loadout]\nteam_color_id = 78\n",
        )
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "linked.toml"\nteam = 0\n'
            'type = "Psyonix"\nskill = "Rookie"\n'
            'name = "Override"\nloadout_file = "other.toml"\n',
        )
        m = load_match_config(p)
        variety = m.player_configurations[0].variety
        assert isinstance(variety, flat.PsyonixBot)
        bot = _psyonix(variety)
        assert bot.bot_skill == flat.PsyonixSkill.Pro
        assert bot.name == "Override"
        assert _loadout(bot.loadout).team_color_id == 77


class TestInvalidSkillIgnored:
    """Check invalid skill is ignored for some entries."""

    def test_invalid_skill_on_human_is_ignored(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nteam = 0\ntype = "Human"\nskill = "NotASkill"\n',
        )
        m = load_match_config(p)
        assert isinstance(m.player_configurations[0].variety, flat.Human)

    def test_invalid_skill_on_custom_file_backed_is_ignored(self, tmp_path: Path):
        make_bot(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bot.toml"\nteam = 0\nskill = "NotASkill"\n',
        )
        m = load_match_config(p)
        assert isinstance(m.player_configurations[0].variety, flat.CustomBot)


class TestScriptValidation:
    """Check script entries need a config file."""

    def test_script_without_config_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[[scripts]]\n")
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_script_without_config_but_auto_start_still_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[[scripts]]\nauto_start = false\n")
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_script_with_config_loads_fields(self, tmp_path: Path):
        make_script(tmp_path)
        p = write(tmp_path / "m.toml", '[[scripts]]\nconfig_file = "script.toml"\n')
        m = load_match_config(p)
        s = m.script_configurations[0]
        assert s.name == "Test Script"
        assert s.agent_id == "test/script"
        assert s.run_command != ""
        assert s.root_dir != ""


class TestTypeValidation:
    """Check wrong types raise ConfigParsingException."""

    def test_string_for_bool_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", '[match]\nenable_rendering = "false"\n')
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_bad_launcher_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", '[rlbot]\nlauncher = "NonExistent"\n')
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_bad_team_raises(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nteam = 42\ntype = "Psyonix"\n',
        )
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_bad_player_type_raises(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nteam = 0\ntype = "NotARobot"\n',
        )
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_script_missing_settings_returns_defaults(self, tmp_path: Path):
        p = write(tmp_path / "empty.toml", "")
        cfg = load_script_config(p)
        assert cfg.name == ""
        assert cfg.agent_id == ""
        assert cfg.run_command == ""
        assert list(_script_env(cfg)) == []

    def test_loadout_int_type_error_raises(self, tmp_path: Path):
        p = write(
            tmp_path / "loadout.toml",
            '[blue_loadout]\nteam_color_id = "red"\n'
            "[orange_loadout]\nteam_color_id = 1\n",
        )
        with pytest.raises(ConfigParsingException):
            load_player_loadout(p, 0)

    def test_team_bool_raises(self, tmp_path: Path):
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nteam = true\ntype = "Human"\n',
        )
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_integer_enum_value_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "[match]\ngame_mode = 1\n")
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    @pytest.mark.parametrize("value", ["-1", "999"])
    def test_out_of_range_numeric_enum_raises(self, tmp_path: Path, value: str):
        path = write(tmp_path / "m.toml", f'[mutators]\nseries_length = "{value}"\n')
        with pytest.raises(ConfigParsingException, match="series_length"):
            load_match_config(path)

    def test_non_list_cars_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", 'cars = "nope"\n')
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_non_table_car_entry_raises(self, tmp_path: Path):
        p = write(tmp_path / "m.toml", "cars = [42]\n")
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_wrong_type_auto_start_raises(self, tmp_path: Path):
        make_bot(tmp_path)
        p = write(
            tmp_path / "m.toml",
            '[[cars]]\nconfig_file = "bot.toml"\nteam = 0\nauto_start = "true"\n',
        )
        with pytest.raises(ConfigParsingException):
            load_match_config(p)

    def test_loadout_unsigned_id_range_raises(self, tmp_path: Path):
        p = write(
            tmp_path / "loadout.toml",
            "[blue_loadout]\nteam_color_id = -1\n[orange_loadout]\nteam_color_id = 1\n",
        )
        with pytest.raises(ConfigParsingException):
            load_player_loadout(p, 0)

        p = write(
            tmp_path / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 4294967296\n"
            "[orange_loadout]\nteam_color_id = 1\n",
        )
        with pytest.raises(ConfigParsingException):
            load_player_loadout(p, 0)


class TestPaintBehavior:
    """Check paint defaults and values."""

    def test_missing_paint_gives_zeroed_paint(self, tmp_path: Path):
        p = write(
            tmp_path / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 5\n[orange_loadout]\nteam_color_id = 6\n",
        )
        blue = load_player_loadout(p, 0)
        orange = load_player_loadout(p, 1)
        assert blue.loadout_paint is not None
        assert orange.loadout_paint is not None
        assert blue.loadout_paint.car_paint_id == 0
        assert orange.loadout_paint.car_paint_id == 0
        assert blue.loadout_paint.trails_paint_id == 0

    def test_present_paint_values_preserved(self):
        blue = load_player_loadout(DIR / "atba" / "loadout.toml", 0)
        orange = load_player_loadout(DIR / "atba" / "loadout.toml", 1)
        assert blue.loadout_paint is not None
        assert orange.loadout_paint is not None
        assert blue.loadout_paint.car_paint_id == 9
        assert orange.loadout_paint.car_paint_id == 1
        assert blue.loadout_paint.boost_paint_id == 5
        assert orange.loadout_paint.goal_explosion_paint_id == 10

    def test_team_selects_correct_loadout_table(self, tmp_path: Path):
        p = write(
            tmp_path / "loadout.toml",
            "[blue_loadout]\nteam_color_id = 31\n"
            "[orange_loadout]\nteam_color_id = 32\n",
        )
        assert load_player_loadout(p, 0).team_color_id == 31
        assert load_player_loadout(p, 1).team_color_id == 32

    def test_invalid_team_does_not_select_orange_loadout(self, tmp_path: Path):
        path = write(tmp_path / "loadout.toml", "[orange_loadout]\ncar_id = 23\n")
        with pytest.raises(ConfigParsingException, match="team"):
            load_player_loadout(path, 2)
