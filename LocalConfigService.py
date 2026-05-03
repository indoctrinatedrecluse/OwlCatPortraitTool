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
        "recent_files": [],
        "selected_booru": "Safebooru",
        "selected_tab": 0,
        "window": {
            "x": 100,
            "y": 100,
            "width": 800,
            "height": 600,
        },
        "recent_exports": {
            "local": "",
            "game": "",
        },
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
    normalized["window"] = default_config["window"].copy()
    normalized["recent_exports"] = default_config["recent_exports"].copy()
    normalized["games"] = {
        game_name: game_settings.copy()
        for game_name, game_settings in default_config["games"].items()
    }

    if isinstance(config, dict):
        if config.get("selected_game") in normalized["games"]:
            normalized["selected_game"] = config["selected_game"]

        saved_booru = config.get("selected_booru")
        if isinstance(saved_booru, str):
            normalized["selected_booru"] = saved_booru

        saved_recent_files = config.get("recent_files")
        if isinstance(saved_recent_files, list):
            # Ensure all items are strings
            normalized["recent_files"] = [str(p) for p in saved_recent_files if isinstance(p, str)]

        selected_tab = config.get("selected_tab")
        if isinstance(selected_tab, int) and selected_tab >= 0:
            normalized["selected_tab"] = selected_tab

        saved_window = config.get("window", {})
        if isinstance(saved_window, dict):
            for key in ("x", "y", "width", "height"):
                value = saved_window.get(key)
                if isinstance(value, int):
                    normalized["window"][key] = value

        saved_recent_exports = config.get("recent_exports", {})
        if isinstance(saved_recent_exports, dict):
            for key in ("local", "game"):
                value = saved_recent_exports.get(key)
                if value:
                    normalized["recent_exports"][key] = str(value)

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


def get_selected_booru(config):
    return config.get("selected_booru", "Safebooru")


def set_selected_booru(config, booru_name):
    config["selected_booru"] = str(booru_name)


def get_recent_files(config):
    return config.get("recent_files", [])


def add_recent_file(config, file_path, max_files):
    file_path = str(Path(file_path))
    recent_files = config.get("recent_files", [])
    if file_path in recent_files:
        recent_files.remove(file_path)
    recent_files.insert(0, file_path)
    config["recent_files"] = recent_files[:max_files]


def remove_recent_file(config, file_path):
    file_path = str(Path(file_path))
    recent_files = config.get("recent_files", [])
    if file_path in recent_files:
        recent_files.remove(file_path)


def clear_recent_files(config):
    config["recent_files"] = []


def get_window_settings(config):
    return config["window"].copy()


def set_window_settings(config, x, y, width, height):
    config["window"] = {
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
    }


def get_selected_tab(config):
    return int(config.get("selected_tab", 0))


def set_selected_tab(config, tab_index):
    config["selected_tab"] = int(tab_index)


def get_recent_export_folder(config, export_kind):
    return Path(config["recent_exports"].get(export_kind, ""))


def set_recent_export_folder(config, export_kind, folder):
    if export_kind in config["recent_exports"]:
        config["recent_exports"][export_kind] = str(Path(folder))
