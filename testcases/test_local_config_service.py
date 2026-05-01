import json

import GlobalsService
import LocalConfigService


def test_local_config_file_is_created_with_per_game_paths(tmp_path):
    config_path = tmp_path / "OwlcatPortraitTool.dat"

    config = LocalConfigService.load_config(
        GlobalsService.GAME_CONFIGS,
        GlobalsService.PATHFINDER_KINGMAKER,
        GlobalsService.get_builtin_appdata_locallow_folder,
        path=config_path,
    )

    assert config_path.exists()
    assert config["version"] == LocalConfigService.CONFIG_VERSION
    assert config["selected_game"] == GlobalsService.PATHFINDER_KINGMAKER
    assert GlobalsService.WARHAMMER_ROGUE_TRADER in config["games"]


def test_local_config_normalizes_missing_new_games(tmp_path):
    config_path = tmp_path / "OwlcatPortraitTool.dat"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "selected_game": GlobalsService.PATHFINDER_WRATH,
                "games": {
                    GlobalsService.PATHFINDER_WRATH: {
                        "appdata_locallow_folder": "F:/Custom/Wrath"
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    config = LocalConfigService.load_config(
        GlobalsService.GAME_CONFIGS,
        GlobalsService.PATHFINDER_KINGMAKER,
        GlobalsService.get_builtin_appdata_locallow_folder,
        path=config_path,
    )

    assert config["selected_game"] == GlobalsService.PATHFINDER_WRATH
    assert config["games"][GlobalsService.PATHFINDER_WRATH][
        "appdata_locallow_folder"
    ] == "F:/Custom/Wrath"
    assert GlobalsService.WARHAMMER_DARK_HERESY in config["games"]
