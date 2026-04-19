from pathlib import Path

import GlobalsService as globals_service


def test_available_games_include_supported_pathfinder_titles():
    games = globals_service.get_available_games()

    assert globals_service.PATHFINDER_KINGMAKER in games
    assert globals_service.PATHFINDER_WRATH in games


def test_unknown_game_falls_back_to_kingmaker():
    assert globals_service.get_game_name("Unknown Game") == globals_service.PATHFINDER_KINGMAKER


def test_game_selection_sets_default_appdata_and_output_paths():
    globals_service.set_game_name(globals_service.PATHFINDER_WRATH)

    assert globals_service.settings.game_name == globals_service.PATHFINDER_WRATH
    assert globals_service.settings.appdata_locallow_folder.name == (
        "Pathfinder Wrath Of The Righteous"
    )
    assert globals_service.settings.output_folder == (
        globals_service.settings.appdata_locallow_folder / "Portraits"
    )


def test_manual_appdata_path_updates_portraits_output_folder(tmp_path):
    custom_folder = tmp_path / "WrathProfile"

    globals_service.set_appdata_locallow_folder(custom_folder)

    assert globals_service.settings.appdata_locallow_folder == custom_folder
    assert globals_service.settings.output_folder == custom_folder / "Portraits"


def test_portrait_dimensions_match_selected_game():
    globals_service.set_game_name(globals_service.PATHFINDER_KINGMAKER)
    kingmaker_sizes = globals_service.get_required_portrait_dimensions()

    globals_service.set_game_name(globals_service.PATHFINDER_WRATH)
    wrath_sizes = globals_service.get_required_portrait_dimensions()

    assert [(size.width, size.height) for size in kingmaker_sizes] == [
        (185, 242),
        (330, 432),
        (692, 1024),
    ]
    assert [(size.width, size.height) for size in wrath_sizes] == [
        (188, 244),
        (332, 432),
        (692, 1024),
    ]


def test_default_appdata_paths_live_under_locallow():
    path = globals_service.get_default_appdata_locallow_folder(
        globals_service.PATHFINDER_KINGMAKER
    )

    assert isinstance(path, Path)
    assert "LocalLow" in path.parts
