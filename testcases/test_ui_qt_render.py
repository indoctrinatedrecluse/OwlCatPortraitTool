import re

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

import GlobalsService
import UIQtRender


def test_generate_portrait_folder_name_is_16_uppercase_letters_or_digits():
    folder_name = UIQtRender.generate_portrait_folder_name()

    assert re.fullmatch(r"[A-Z0-9]{16}", folder_name)


def test_create_unique_portrait_folder_creates_under_output_root(tmp_path):
    output_folder = UIQtRender.create_unique_portrait_folder(tmp_path)

    assert output_folder.parent == tmp_path
    assert output_folder.exists()
    assert re.fullmatch(r"[A-Z0-9]{16}", output_folder.name)


def test_image_to_pixmap_preserves_image_size(qt_app):
    image = Image.new("RGBA", (24, 32), (20, 40, 60, 255))

    pixmap = UIQtRender.image_to_pixmap(image)

    assert pixmap.width() == 24
    assert pixmap.height() == 32


def test_crop_canvas_returns_full_length_portrait_size(qt_app):
    canvas = UIQtRender.PortraitCropCanvas()
    canvas.resize(500, 620)
    canvas.set_image(Image.new("RGBA", (1200, 1600), (20, 40, 60, 255)))

    cropped = canvas.get_cropped_image()

    assert cropped.size == (692, 1024)


def test_crop_canvas_paint_event_accepts_float_target_rect(qt_app):
    canvas = UIQtRender.PortraitCropCanvas()
    canvas.resize(500, 620)
    canvas.set_image(Image.new("RGBA", (1200, 1600), (20, 40, 60, 255)))

    target = QtGui.QPixmap(canvas.size())
    canvas.render(target)

    assert not target.isNull()


def test_crop_canvas_drag_constraint_keeps_image_covering_crop(qt_app):
    canvas = UIQtRender.PortraitCropCanvas()
    canvas.resize(500, 620)
    canvas.set_image(Image.new("RGBA", (1200, 1600), (20, 40, 60, 255)))

    canvas.image_offset = QtCore.QPointF(10_000, 10_000)
    canvas.constrain_image_to_crop()
    image_rect = canvas.get_image_rect()
    crop_rect = canvas.get_crop_rect()

    assert image_rect.left() <= crop_rect.left()
    assert image_rect.top() <= crop_rect.top()
    assert image_rect.right() >= crop_rect.right()
    assert image_rect.bottom() >= crop_rect.bottom()


def test_portrait_editor_export_writes_three_pathfinder_images(qt_app, tmp_path):
    GlobalsService.set_game_name(GlobalsService.PATHFINDER_KINGMAKER)
    editor = UIQtRender.PortraitEditorTab()
    editor.resize(600, 760)
    editor.source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    editor.crop_canvas.resize(500, 620)
    editor.crop_canvas.set_image(editor.source_image)

    editor.export_portrait_set(tmp_path)

    export_folders = list(tmp_path.iterdir())
    assert len(export_folders) == 1
    export_folder = export_folders[0]
    assert re.fullmatch(r"[A-Z0-9]{16}", export_folder.name)

    expected_sizes = {
        "Small.png": (185, 242),
        "Medium.png": (330, 432),
        "Fulllength.png": (692, 1024),
    }
    for file_name, expected_size in expected_sizes.items():
        image_path = export_folder / file_name
        assert image_path.exists()
        with Image.open(image_path) as image:
            assert image.size == expected_size


def test_search_tab_direct_url_hands_off_to_portrait_editor(qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: calls.append(url)},
    )()
    tab = UIQtRender.SearchTab(main_window)

    tab.input_switch.setChecked(True)
    tab.search_bar.setText("https://example.com/portrait.png")
    tab.process_search()

    assert calls == ["https://example.com/portrait.png"]


def test_search_result_click_hands_off_to_portrait_editor(qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: calls.append(url)},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    item.setData(QtCore.Qt.UserRole, "https://example.com/result.png")

    tab.open_selected_result(item)

    assert calls == ["https://example.com/result.png"]


def test_search_result_item_clicked_signal_hands_off_to_portrait_editor(qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: calls.append(url)},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    item.setData(QtCore.Qt.UserRole, "https://example.com/clicked.png")
    tab.results_list.addItem(item)

    tab.results_list.itemClicked.emit(item)

    assert calls == ["https://example.com/clicked.png"]


def test_portrait_editor_displays_source_url(monkeypatch, qt_app):
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    editor = UIQtRender.PortraitEditorTab()

    editor.set_source_url("https://example.com/source.png")

    assert "https://example.com/source.png" in editor.source_label.text()
    assert editor.source_url == "https://example.com/source.png"


def test_main_window_result_handoff_switches_to_editor_and_displays_url(monkeypatch, qt_app):
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    window = UIQtRender.MainWindow()

    window.open_portrait_editor_with_url("https://example.com/result-source.png")

    assert window.tab_widget.currentIndex() == UIQtRender.PORTRAIT_EDITOR_TAB_INDEX
    assert "https://example.com/result-source.png" in (
        window.portrait_editor_tab.source_label.text()
    )
    assert window.portrait_editor_tab.source_url == (
        "https://example.com/result-source.png"
    )


def test_search_tab_invalid_url_stays_on_search_results(qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: calls.append(url)},
    )()
    tab = UIQtRender.SearchTab(main_window)

    tab.input_switch.setChecked(True)
    tab.search_bar.setText("not-a-url")
    tab.process_search()

    assert calls == []
    assert tab.results_list.item(0).text() == "Enter a valid HTTP or HTTPS image URL."


def test_settings_tab_game_change_updates_global_paths(qt_app):
    tab = UIQtRender.SettingsTab()

    tab.change_game(GlobalsService.PATHFINDER_WRATH)

    assert GlobalsService.settings.game_name == GlobalsService.PATHFINDER_WRATH
    assert "Wrath Of The Righteous" in tab.appdata_path_label.text()
