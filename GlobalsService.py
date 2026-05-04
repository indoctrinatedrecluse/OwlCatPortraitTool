from dataclasses import dataclass
from pathlib import Path

import LocalConfigService


PATHFINDER_KINGMAKER = "Pathfinder Kingmaker"
PATHFINDER_WRATH = "Pathfinder Wrath of the Righteous"
WARHAMMER_ROGUE_TRADER = "Warhammer 40k: Rogue Trader"
WARHAMMER_DARK_HERESY = "Warhammer 40k: Dark Heresy"
STARFINDER = "Starfinder"

MAX_RECENT_FILES = 10

@dataclass(frozen=True)
class PortraitSize:
    name: str
    width: int
    height: int


@dataclass(frozen=True)
class GameConfig:
    name: str
    appdata_folder_name: str
    portrait_dimensions: tuple[PortraitSize, ...]


@dataclass
class AppSettings:
    game_name: str = PATHFINDER_KINGMAKER
    appdata_locallow_folder: Path | None = None
    output_folder: Path | None = None


settings = AppSettings()

PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS = (
    PortraitSize("Small.png", 185, 242),
    PortraitSize("Medium.png", 330, 432),
    PortraitSize("Fulllength.png", 692, 1024),
)

PATHFINDER_WRATH_PORTRAIT_DIMENSIONS = (
    PortraitSize("Small.png", 188, 244),
    PortraitSize("Medium.png", 332, 432),
    PortraitSize("Fulllength.png", 692, 1024),
)

GAME_CONFIGS = (
    GameConfig(
        PATHFINDER_KINGMAKER,
        "Pathfinder Kingmaker",
        PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS,
    ),
    GameConfig(
        PATHFINDER_WRATH,
        "Pathfinder Wrath Of The Righteous",
        PATHFINDER_WRATH_PORTRAIT_DIMENSIONS,
    ),
    GameConfig(
        WARHAMMER_ROGUE_TRADER,
        "Warhammer 40000 Rogue Trader",
        PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS,
    ),
    GameConfig(
        WARHAMMER_DARK_HERESY,
        "WHDH",
        PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS,
    ),
    GameConfig(
        STARFINDER,
        "Starfinder",
        PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS,
    ),
)
GAME_CONFIGS_BY_NAME = {game_config.name: game_config for game_config in GAME_CONFIGS}
OWLCAT_LOCALLOW_ROOT = Path.home() / "AppData" / "LocalLow" / "Owlcat Games"
local_config = None
local_config_path = None


def get_available_games():
    return [game_config.name for game_config in GAME_CONFIGS]


def get_game_config(game_name=None):
    return GAME_CONFIGS_BY_NAME[get_game_name(game_name)]


def get_next_game_name(game_name=None):
    games = get_available_games()
    current_game = get_game_name(game_name)
    current_index = games.index(current_game)
    return games[(current_index + 1) % len(games)]


def get_builtin_appdata_locallow_folder(game_name=None):
    return OWLCAT_LOCALLOW_ROOT / get_game_config(game_name).appdata_folder_name


def get_default_appdata_locallow_folder(game_name=None):
    game_name = get_game_name(game_name)
    if local_config is None:
        return get_builtin_appdata_locallow_folder(game_name)

    return LocalConfigService.get_game_appdata_folder(local_config, game_name)


def get_required_portrait_dimensions(game_name=None):
    return get_game_config(game_name).portrait_dimensions


def get_full_length_portrait_size(game_name=None):
    return get_required_portrait_dimensions(game_name)[-1]


def get_game_name(game_name=None):
    if game_name is None:
        game_name = settings.game_name

    if game_name not in GAME_CONFIGS_BY_NAME:
        return PATHFINDER_KINGMAKER

    return game_name


def load_local_config(path=None):
    global local_config, local_config_path

    local_config_path = path
    local_config = LocalConfigService.load_config(
        GAME_CONFIGS,
        PATHFINDER_KINGMAKER,
        get_builtin_appdata_locallow_folder,
        path=path,
    )
    return local_config


def save_local_config(path=None):
    if local_config is not None:
        LocalConfigService.save_config(
            local_config,
            path=path if path is not None else local_config_path,
        )


def get_window_settings():
    return LocalConfigService.get_window_settings(local_config)


def set_window_settings(x, y, width, height, save=True):
    if local_config is None:
        return

    LocalConfigService.set_window_settings(local_config, x, y, width, height)
    if save:
        save_local_config()


def get_selected_tab():
    return LocalConfigService.get_selected_tab(local_config)


def set_selected_tab(tab_index, save=True):
    if local_config is None:
        return

    LocalConfigService.set_selected_tab(local_config, tab_index)
    if save:
        save_local_config()


def get_recent_export_folder(export_kind):
    return LocalConfigService.get_recent_export_folder(local_config, export_kind)


def set_recent_export_folder(export_kind, folder, save=True):
    if local_config is None:
        return

    LocalConfigService.set_recent_export_folder(local_config, export_kind, folder)
    if save:
        save_local_config()


def get_recent_files():
    """Return the list of recently opened file paths."""
    if local_config is None:
        return []
    return LocalConfigService.get_recent_files(local_config)


def add_recent_file(file_path, save=True):
    """Add a file to the top of the recent files list."""
    if local_config is None:
        return
    LocalConfigService.add_recent_file(local_config, file_path, max_files=MAX_RECENT_FILES)
    if save:
        save_local_config()


def remove_recent_file(file_path, save=True):
    """Remove a file from the recent files list."""
    if local_config is None:
        return
    LocalConfigService.remove_recent_file(local_config, file_path)
    if save:
        save_local_config()


def clear_recent_files(save=True):
    """Clear all files from the recent files list."""
    if local_config is None:
        return
    LocalConfigService.clear_recent_files(local_config)
    if save:
        save_local_config()


def get_selected_booru():
    """Return the last-selected booru site name from local config."""
    if local_config is None:
        return "Safebooru"

    return LocalConfigService.get_selected_booru(local_config)


def set_selected_booru(booru_name, save=True):
    """Update the last-selected booru site name in local config."""
    if local_config is None:
        return

    LocalConfigService.set_selected_booru(local_config, booru_name)
    if save:
        save_local_config()


def set_game_name(game_name, save=True):
    global GAME_NAME, APPDATA_LOCALLOW_FOLDER, OUTPUT_FOLDER
    global REQUIRED_PORTRAIT_DIMENSIONS, FULL_LENGTH_PORTRAIT_SIZE

    settings.game_name = get_game_name(game_name)
    if save and local_config is not None:
        LocalConfigService.set_selected_game(local_config, settings.game_name)
        save_local_config()

    settings.appdata_locallow_folder = get_default_appdata_locallow_folder(
        settings.game_name
    )
    settings.output_folder = settings.appdata_locallow_folder / "Portraits"
    GAME_NAME = settings.game_name
    APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
    OUTPUT_FOLDER = settings.output_folder
    REQUIRED_PORTRAIT_DIMENSIONS = get_required_portrait_dimensions()
    FULL_LENGTH_PORTRAIT_SIZE = get_full_length_portrait_size()


def set_appdata_locallow_folder(folder, save=True):
    global APPDATA_LOCALLOW_FOLDER, OUTPUT_FOLDER

    settings.appdata_locallow_folder = Path(folder)
    settings.output_folder = settings.appdata_locallow_folder / "Portraits"
    if save and local_config is not None:
        LocalConfigService.set_game_appdata_folder(
            local_config,
            settings.game_name,
            settings.appdata_locallow_folder,
        )
        save_local_config()

    APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
    OUTPUT_FOLDER = settings.output_folder


load_local_config()
set_game_name(local_config["selected_game"], save=False)

REQUIRED_PORTRAIT_DIMENSIONS = get_required_portrait_dimensions()
FULL_LENGTH_PORTRAIT_SIZE = get_full_length_portrait_size()

# Backward-compatible names for modules that still import constants directly.
GAME_NAME = settings.game_name
APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
OUTPUT_FOLDER = settings.output_folder
