import json
import sys
from pathlib import Path


CONFIG_VERSION = 1
CONFIG_FILE_NAME = "OwlcatPortraitTool.dat"


def get_default_config_file_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name(CONFIG_FILE_NAME)

    return Path(__file__).resolve().with_name(CONFIG_FILE_NAME)


CONFIG_FILE_PATH = get_default_config_file_path()


def build_default_config(game_configs, default_game_name, default_path_provider):
    return {
        "version": CONFIG_VERSION,
        "selected_game": default_game_name,
        "games": {
            game_config.name: {
                "appdata_locallow_folder": str(default_path_provider(game_config.name))
            }
            for game_config in game_configs
        },
    }


def ensure_config_file(game_configs, default_game_name, default_path_provider, path=None):
    config_path = Path(path) if path is not None else CONFIG_FILE_PATH
    if config_path.exists():
        return config_path

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            build_default_config(game_configs, default_game_name, default_path_provider),
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path


def load_config(game_configs, default_game_name, default_path_provider, path=None):
    config_path = ensure_config_file(
        game_configs,
        default_game_name,
        default_path_provider,
        path=path,
    )

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}

    default_config = build_default_config(
        game_configs,
        default_game_name,
        default_path_provider,
    )
    return normalize_config(config, default_config)


def normalize_config(config, default_config):
    normalized = default_config.copy()
    normalized["games"] = {
        game_name: game_settings.copy()
        for game_name, game_settings in default_config["games"].items()
    }

    if isinstance(config, dict):
        if config.get("selected_game") in normalized["games"]:
            normalized["selected_game"] = config["selected_game"]

        saved_games = config.get("games", {})
        if isinstance(saved_games, dict):
            for game_name, game_settings in saved_games.items():
                if game_name not in normalized["games"]:
                    continue
                if not isinstance(game_settings, dict):
                    continue

                saved_folder = game_settings.get("appdata_locallow_folder")
                if saved_folder:
                    normalized["games"][game_name]["appdata_locallow_folder"] = str(
                        saved_folder
                    )

    return normalized


def save_config(config, path=None):
    config_path = Path(path) if path is not None else CONFIG_FILE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_game_appdata_folder(config, game_name):
    return Path(config["games"][game_name]["appdata_locallow_folder"])


def set_game_appdata_folder(config, game_name, folder):
    config["games"][game_name]["appdata_locallow_folder"] = str(Path(folder))


def set_selected_game(config, game_name):
    if game_name in config["games"]:
        config["selected_game"] = game_name
