import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5 import QtWidgets


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import GlobalsService


@pytest.fixture(autouse=True)
def reset_global_settings():
    config_path = PROJECT_ROOT / "testcases" / "_tmp" / "OwlcatPortraitTool.dat"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        config_path.unlink()
    GlobalsService.load_local_config(path=config_path)
    GlobalsService.set_game_name(GlobalsService.PATHFINDER_KINGMAKER)
    yield
    GlobalsService.load_local_config(path=config_path)
    GlobalsService.set_game_name(GlobalsService.PATHFINDER_KINGMAKER)


@pytest.fixture
def tmp_path(request):
    base_path = PROJECT_ROOT / "testcases" / "_tmp" / request.node.name
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)

    yield base_path

    if base_path.exists():
        shutil.rmtree(base_path)


@pytest.fixture(scope="session")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    return app
