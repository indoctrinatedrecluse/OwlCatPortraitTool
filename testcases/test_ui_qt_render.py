import re
from io import BytesIO

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

import GlobalsService
import UIQtRender
from RequestHeaders import IMAGE_REQUEST_HEADERS
from SearchService import PortraitSearchResult


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


def test_load_preview_image_retries_with_preview_timeout(monkeypatch, qt_app):
    calls = []
    preview_image = Image.new("RGBA", (16, 24), (20, 40, 60, 255))
    image_bytes = BytesIO()
    preview_image.save(image_bytes, format="PNG")

    class FakeResponse:
        content = image_bytes.getvalue()

        def raise_for_status(self):
            return None

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        if len(calls) < UIQtRender.MAX_PREVIEW_LOAD_ATTEMPTS:
            raise RuntimeError("temporary failure")
        return FakeResponse()

    monkeypatch.setattr(UIQtRender.requests, "get", fake_get)
    result = PortraitSearchResult(
        "https://example.com/full.png",
        preview_url="https://example.com/preview.png",
    )

    loaded_image = UIQtRender.load_preview_image(result)

    assert len(calls) == UIQtRender.MAX_PREVIEW_LOAD_ATTEMPTS
    assert all(call[2] == UIQtRender.PREVIEW_REQUEST_TIMEOUT_SECONDS for call in calls)
    assert all(call[1] == IMAGE_REQUEST_HEADERS for call in calls)
    assert loaded_image.width() == 16
    assert loaded_image.height() == 24


def test_load_preview_image_fails_after_retry_limit(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        raise RuntimeError("still down")

    monkeypatch.setattr(UIQtRender.requests, "get", fake_get)
    result = PortraitSearchResult("https://example.com/full.png")

    try:
        UIQtRender.load_preview_image(result)
    except RuntimeError as error:
        assert f"{UIQtRender.MAX_PREVIEW_LOAD_ATTEMPTS} attempts" in str(error)
    else:
        raise AssertionError("Expected preview loading to fail after retries.")

    assert len(calls) == UIQtRender.MAX_PREVIEW_LOAD_ATTEMPTS


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
    editor.has_unsaved_changes = True
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
    assert not editor.has_unsaved_changes


def test_portrait_editor_loaded_image_starts_clean_and_crop_change_marks_dirty(
    monkeypatch,
    qt_app,
):
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    editor = UIQtRender.PortraitEditorTab()

    editor.set_source_url("https://example.com/source.png")
    editor.crop_canvas.cropChanged.emit()

    assert editor.source_url == "https://example.com/source.png"
    assert editor.has_unsaved_changes


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
    item.setData(UIQtRender.RESULT_IMAGE_URL_ROLE, "https://example.com/result.png")

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
    item.setData(UIQtRender.RESULT_IMAGE_URL_ROLE, "https://example.com/clicked.png")
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


def test_main_window_clean_close_uses_generic_confirmation(qt_app):
    calls = []
    window = UIQtRender.MainWindow()
    window.confirm_close_application = lambda: calls.append("close") or False
    window.confirm_leave_portrait_editor = lambda: calls.append("editor") or False
    window.portrait_editor_tab.has_unsaved_changes = False
    event = QtGui.QCloseEvent()

    window.closeEvent(event)

    assert calls == ["close"]
    assert not event.isAccepted()


def test_main_window_dirty_close_uses_unsaved_editor_confirmation(qt_app):
    calls = []
    window = UIQtRender.MainWindow()
    window.confirm_close_application = lambda: calls.append("close") or False
    window.confirm_leave_portrait_editor = lambda: calls.append("editor") or False
    window.portrait_editor_tab.has_unsaved_changes = True
    event = QtGui.QCloseEvent()

    window.closeEvent(event)

    assert calls == ["editor"]
    assert not event.isAccepted()


def test_dirty_portrait_editor_blocks_tab_change_when_user_cancels(qt_app):
    calls = []
    window = UIQtRender.MainWindow()
    window.confirm_leave_portrait_editor = lambda: calls.append("editor") or False
    window.portrait_editor_tab.has_unsaved_changes = True

    window.tab_widget.setCurrentIndex(1)

    assert calls == ["editor"]
    assert window.tab_widget.currentIndex() == UIQtRender.PORTRAIT_EDITOR_TAB_INDEX


def test_dirty_portrait_editor_allows_tab_change_when_user_confirms(qt_app):
    calls = []
    window = UIQtRender.MainWindow()
    window.confirm_leave_portrait_editor = lambda: calls.append("editor") or True
    window.portrait_editor_tab.has_unsaved_changes = True

    window.tab_widget.setCurrentIndex(1)

    assert calls == ["editor"]
    assert window.tab_widget.currentIndex() == 1


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


def test_search_preview_thread_pool_has_bounded_concurrency(qt_app):
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)

    assert tab.preview_thread_pool.maxThreadCount() == (
        UIQtRender.MAX_CONCURRENT_PREVIEW_LOADS
    )


def test_search_clears_queued_preview_loads_when_new_search_starts(monkeypatch, qt_app):
    started_workers = []
    clear_calls = []

    class FakeThreadPool:
        def clear(self):
            clear_calls.append(True)

        def start(self, worker):
            started_workers.append(worker)

    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    tab.preview_thread_pool = FakeThreadPool()
    tab.input_switch.setChecked(False)
    tab.search_bar.setText("portrait")
    monkeypatch.setattr(
        UIQtRender,
        "search_portraits_by_tags",
        lambda tags: [
            PortraitSearchResult("https://example.com/one.png"),
            PortraitSearchResult("https://example.com/two.png"),
        ],
    )

    tab.process_search()

    assert clear_calls == [True]
    assert len(started_workers) == 2
    assert started_workers[0].generation == tab.preview_generation


def test_stale_preview_success_cannot_update_current_results(qt_app):
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    image_label = QtWidgets.QLabel("Loading...")
    tab.image_result_widgets = [(item, image_label, None)]
    tab.preview_generation = 2

    image = QtGui.QImage(12, 16, QtGui.QImage.Format_RGBA8888)
    tab.preview_loaded(1, 0, image)

    assert image_label.text() == "Loading..."
    assert tab.image_result_widgets[0][2] is None


def test_stale_preview_failure_cannot_update_current_results(qt_app):
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    image_label = QtWidgets.QLabel("Loading...")
    image_label.setToolTip("https://example.com/portrait.png")
    tab.image_result_widgets = [(item, image_label, None)]
    tab.preview_generation = 2

    tab.preview_failed(1, 0, "timed out")

    assert image_label.text() == "Loading..."
    assert image_label.toolTip() == "https://example.com/portrait.png"


def test_current_preview_failure_marks_placeholder(qt_app):
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    image_label = QtWidgets.QLabel("Loading...")
    image_label.setToolTip("https://example.com/portrait.png")
    tab.image_result_widgets = [(item, image_label, None)]
    tab.preview_generation = 2

    tab.preview_failed(2, 0, "network timed out")

    assert image_label.text() == "Preview failed"
    assert item.data(UIQtRender.RESULT_PREVIEW_FAILURE_ROLE) == "network timed out"
    assert "network timed out" in image_label.toolTip()


def test_failed_preview_click_shows_message_and_does_not_open_editor(qt_app):
    calls = []
    messages = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: calls.append(url)},
    )()
    tab = UIQtRender.SearchTab(main_window)
    tab.show_preview_failure_message = lambda message: messages.append(message)
    item = QtWidgets.QListWidgetItem()
    item.setData(UIQtRender.RESULT_IMAGE_URL_ROLE, "https://example.com/result.png")
    item.setData(UIQtRender.RESULT_PREVIEW_FAILURE_ROLE, "failed after retries")

    tab.open_selected_result(item)

    assert calls == []
    assert messages == ["failed after retries"]


def test_current_preview_success_updates_current_result(qt_app):
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    item = QtWidgets.QListWidgetItem()
    image_label = QtWidgets.QLabel("Loading...")
    tab.image_result_widgets = [(item, image_label, None)]
    tab.preview_generation = 2
    tab.results_list.setIconSize(QtCore.QSize(24, 32))

    image = QtGui.QImage(12, 16, QtGui.QImage.Format_RGBA8888)
    tab.preview_loaded(2, 0, image)

    assert image_label.text() == ""
    assert tab.image_result_widgets[0][2] is not None
    assert image_label.pixmap() is not None


def test_search_close_cancels_queued_preview_loads_and_waits_briefly(qt_app):
    calls = []

    class FakeThreadPool:
        def clear(self):
            calls.append(("clear", None))

        def waitForDone(self, timeout):
            calls.append(("waitForDone", timeout))
            return True

    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    tab.preview_thread_pool = FakeThreadPool()

    tab.closeEvent(QtGui.QCloseEvent())

    assert calls == [("clear", None), ("waitForDone", 100)]


def test_settings_tab_game_change_updates_global_paths(qt_app):
    tab = UIQtRender.SettingsTab()

    tab.change_game(GlobalsService.PATHFINDER_WRATH)

    assert GlobalsService.settings.game_name == GlobalsService.PATHFINDER_WRATH
    assert "Wrath Of The Righteous" in tab.appdata_path_label.text()
