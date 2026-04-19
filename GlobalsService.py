from dataclasses import dataclass
from pathlib import Path


PATHFINDER_KINGMAKER = "Pathfinder Kingmaker"
PATHFINDER_WRATH = "Pathfinder Wrath of the Righteous"


@dataclass(frozen=True)
class PortraitSize:
    name: str
    width: int
    height: int


@dataclass
class AppSettings:
    game_name: str = PATHFINDER_KINGMAKER
    appdata_locallow_folder: Path | None = None
    output_folder: Path | None = None


settings = AppSettings()

DEFAULT_APPDATA_LOCALLOW_PATHS_BY_GAME = {
    PATHFINDER_KINGMAKER: Path.home()
    / "AppData"
    / "LocalLow"
    / "Owlcat Games"
    / "Pathfinder Kingmaker",
    PATHFINDER_WRATH: Path.home()
    / "AppData"
    / "LocalLow"
    / "Owlcat Games"
    / "Pathfinder Wrath Of The Righteous",
}

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

PORTRAIT_DIMENSIONS_BY_GAME = {
    PATHFINDER_KINGMAKER: PATHFINDER_KINGMAKER_PORTRAIT_DIMENSIONS,
    PATHFINDER_WRATH: PATHFINDER_WRATH_PORTRAIT_DIMENSIONS,
}


def get_available_games():
    return list(PORTRAIT_DIMENSIONS_BY_GAME.keys())


def get_default_appdata_locallow_folder(game_name=None):
    return DEFAULT_APPDATA_LOCALLOW_PATHS_BY_GAME[get_game_name(game_name)]


def get_required_portrait_dimensions(game_name=None):
    return PORTRAIT_DIMENSIONS_BY_GAME[get_game_name(game_name)]


def get_full_length_portrait_size(game_name=None):
    return get_required_portrait_dimensions(game_name)[-1]


def get_game_name(game_name=None):
    if game_name is None:
        game_name = settings.game_name

    if game_name not in PORTRAIT_DIMENSIONS_BY_GAME:
        return PATHFINDER_KINGMAKER

    return game_name


def set_game_name(game_name):
    global GAME_NAME, APPDATA_LOCALLOW_FOLDER, OUTPUT_FOLDER
    global REQUIRED_PORTRAIT_DIMENSIONS, FULL_LENGTH_PORTRAIT_SIZE

    settings.game_name = get_game_name(game_name)
    settings.appdata_locallow_folder = get_default_appdata_locallow_folder(
        settings.game_name
    )
    settings.output_folder = settings.appdata_locallow_folder / "Portraits"
    GAME_NAME = settings.game_name
    APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
    OUTPUT_FOLDER = settings.output_folder
    REQUIRED_PORTRAIT_DIMENSIONS = get_required_portrait_dimensions()
    FULL_LENGTH_PORTRAIT_SIZE = get_full_length_portrait_size()


def set_appdata_locallow_folder(folder):
    global APPDATA_LOCALLOW_FOLDER, OUTPUT_FOLDER

    settings.appdata_locallow_folder = Path(folder)
    settings.output_folder = settings.appdata_locallow_folder / "Portraits"
    APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
    OUTPUT_FOLDER = settings.output_folder


set_game_name(settings.game_name)

REQUIRED_PORTRAIT_DIMENSIONS = get_required_portrait_dimensions()
FULL_LENGTH_PORTRAIT_SIZE = get_full_length_portrait_size()

# Backward-compatible names for modules that still import constants directly.
GAME_NAME = settings.game_name
APPDATA_LOCALLOW_FOLDER = settings.appdata_locallow_folder
OUTPUT_FOLDER = settings.output_folder
