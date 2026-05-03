import re
from io import BytesIO

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

import GlobalsService
import UIQtRender
import SearchService
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


def test_portrait_editor_has_separate_local_and_appdata_export_buttons(qt_app):
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)

    assert editor.export_local_button.text() == "Export To Local Output"
    assert editor.export_game_button.text() == "Export To AppData/Portraits"


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
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)
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

    assert editor.export_path_field.text() == str(export_folder)
    assert editor.copy_path_button.isEnabled()
    assert "successful" in editor.status_label.text()


def test_portrait_editor_copy_path_button_and_state_changes(monkeypatch, qt_app):
    # Test 1: Copy button copies path to clipboard
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)
    editor.export_path_field.setText("F:/fake/path/to/export")
    clipboard = QtWidgets.QApplication.clipboard()
    clipboard.clear()
    editor.copy_export_path()
    assert clipboard.text() == "F:/fake/path/to/export"
    assert "Copied" in editor.status_label.text()

    # Test 2: Loading a new source clears the path
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    editor.copy_path_button.setEnabled(True)
    editor.set_source_url("https://example.com/source.png")
    assert editor.export_path_field.text() == ""
    assert not editor.copy_path_button.isEnabled()


def test_portrait_editor_loaded_image_starts_clean_and_crop_change_marks_dirty(
    monkeypatch,
    qt_app,
):
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)

    editor.set_source_url("https://example.com/source.png")
    editor.crop_canvas.cropChanged.emit()

    assert editor.source_url == "https://example.com/source.png"
    assert editor.has_unsaved_changes


def test_portrait_editor_pastes_clipboard_image(qt_app):
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)
    clipboard = QtWidgets.QApplication.clipboard()

    # 1. Test pasting non-image data (should do nothing)
    clipboard.setText("this is not an image")
    event = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress, QtCore.Qt.Key_P, QtCore.Qt.ControlModifier
    )
    QtWidgets.QApplication.sendEvent(editor, event)
    assert editor.source_image is None

    # 2. Test pasting an image
    pil_image = Image.new("RGBA", (100, 120), "blue")
    q_image = UIQtRender.image_to_pixmap(pil_image).toImage()
    clipboard.setImage(q_image)

    QtWidgets.QApplication.sendEvent(editor, event)

    assert editor.source_image is not None
    assert editor.source_image.size == (100, 120)
    assert "Pasted from clipboard" in editor.source_label.text()


def test_portrait_editor_tab_shows_dirty_indicator(monkeypatch, qt_app):
    window = UIQtRender.MainWindow()
    editor = window.portrait_editor_tab
    tab_widget = window.tab_widget
    tab_bar = tab_widget.tabBar()
    original_color = window.original_tab_color

    # 1. Initial state is clean
    assert tab_widget.tabText(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == "Portrait Editor"
    assert tab_bar.tabTextColor(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == original_color

    # 2. Mark dirty
    editor.source_image = Image.new("RGBA", (10, 10))
    editor.set_dirty_state(True)
    assert tab_widget.tabText(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == "Portrait Editor *"
    assert tab_bar.tabTextColor(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == QtGui.QColor("orange")

    # 3. Mark clean
    editor.set_dirty_state(False)
    assert tab_widget.tabText(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == "Portrait Editor"
    assert tab_bar.tabTextColor(UIQtRender.PORTRAIT_EDITOR_TAB_INDEX) == original_color


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


def test_search_tab_clear_button_clears_input_and_results(monkeypatch, qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)
    monkeypatch.setattr(tab, "cancel_preview_loads", lambda: calls.append("cancel"))

    # Given: search bar and results have content
    tab.search_bar.setText("test search")
    tab.results_list.addItem("An item")
    tab.image_result_widgets = ["dummy widget"]

    # When: clear button is clicked
    tab.clear_button.click()

    # Then: search bar and results are cleared
    assert tab.search_bar.text() == ""
    assert tab.results_list.count() == 0
    assert tab.image_result_widgets == []
    assert calls == ["cancel"]


def test_search_tab_uses_selected_booru(monkeypatch, qt_app):
    calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)

    def mock_search(tags, booru_name, page=1, limit=50):
        calls.append((tags, booru_name, page))
        return []

    monkeypatch.setattr(UIQtRender, "search_portraits_by_tags", mock_search)

    tab.input_switch.setChecked(False)
    tab.search_bar.setText("test_tag")

    danbooru_index = tab.booru_selector.findText("Danbooru")
    assert danbooru_index != -1
    tab.booru_selector.setCurrentIndex(danbooru_index)

    tab.process_search()

    assert len(calls) == 1
    assert calls[0][0] == ["test_tag"]
    assert calls[0][1] == "Danbooru"
    assert calls[0][2] == 1


def test_search_tab_pagination_buttons_work(monkeypatch, qt_app):
    search_calls = []
    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)

    def mock_execute_search():
        search_calls.append(tab.current_page)

    monkeypatch.setattr(tab, "execute_tag_search", mock_execute_search)

    # Given: on page 2
    tab.current_page = 2

    # When: next is clicked
    tab.next_button.click()
    assert search_calls == [3]

    # When: prev is clicked
    tab.prev_button.click()
    assert search_calls == [3, 2]


def test_search_tab_remembers_last_selected_booru(monkeypatch, qt_app):
    set_booru_calls = []
    monkeypatch.setattr(UIQtRender, "get_selected_booru", lambda: "Danbooru")
    monkeypatch.setattr(
        UIQtRender, "set_selected_booru", lambda name: set_booru_calls.append(name)
    )

    main_window = type(
        "FakeMainWindow",
        (),
        {"open_portrait_editor_with_url": lambda self, url: None},
    )()
    tab = UIQtRender.SearchTab(main_window)

    assert tab.booru_selector.currentText() == "Danbooru"

    konachan_index = tab.booru_selector.findText("Konachan")
    assert konachan_index != -1
    tab.booru_selector.setCurrentIndex(konachan_index)

    assert set_booru_calls == ["Konachan"]


def test_portrait_editor_displays_source_url(monkeypatch, qt_app):
    source_image = Image.new("RGBA", (1200, 1600), (50, 100, 150, 255))
    monkeypatch.setattr(UIQtRender, "get_image_from_url", lambda url: source_image)
    main_window_mock = type(
        "FakeMainWindow",
        (),
        {
            "open_local_image_dialog": lambda: None,
            "ensure_current_game_path_exists": lambda: True,
        },
    )()
    editor = UIQtRender.PortraitEditorTab(main_window_mock)

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
        lambda tags, booru_name, page=1: [
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
    assert tab.target_game_button.text() == GlobalsService.PATHFINDER_WRATH
    assert "Wrath Of The Righteous" in tab.appdata_path_label.text()


def test_settings_tab_switch_target_game_button_cycles_games(qt_app):
    GlobalsService.set_game_name(GlobalsService.PATHFINDER_KINGMAKER)
    tab = UIQtRender.SettingsTab()
    tab.ensure_current_game_path_exists = lambda: True

    tab.switch_target_game()

    assert GlobalsService.settings.game_name == GlobalsService.PATHFINDER_WRATH
    assert tab.target_game_button.text() == GlobalsService.PATHFINDER_WRATH


def test_settings_tab_missing_game_path_opens_folder_picker(monkeypatch, qt_app):
    messages = []
    selected_folder = "F:/Custom/Owlcat"
    tab = UIQtRender.SettingsTab()
    GlobalsService.set_appdata_locallow_folder("F:/Missing/Owlcat")
    tab.refresh_path_labels()

    monkeypatch.setattr(
        UIQtRender.QtWidgets.QMessageBox,
        "warning",
        lambda *args: messages.append(args),
    )
    monkeypatch.setattr(
        UIQtRender.QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *args: selected_folder,
    )

    assert tab.ensure_current_game_path_exists()
    assert messages
    assert GlobalsService.settings.appdata_locallow_folder.as_posix() == selected_folder


def test_main_window_drag_drop_overlay(monkeypatch, qt_app):
    open_calls = []
    window = UIQtRender.MainWindow()
    monkeypatch.setattr(
        window, "open_portrait_editor_with_file", lambda path: open_calls.append(path)
    )

    # 1. Drag enter with invalid data
    invalid_mime = QtCore.QMimeData()
    invalid_mime.setText("not a file")
    drag_enter_event = QtGui.QDragEnterEvent(
        QtCore.QPoint(10, 10), QtCore.Qt.CopyAction, invalid_mime, QtCore.Qt.NoButton, QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(window, drag_enter_event)
    assert not window.drop_overlay.isVisible()
    assert not drag_enter_event.isAccepted()

    # 2. Drag enter with valid image file
    valid_mime = QtCore.QMimeData()
    url = QtCore.QUrl.fromLocalFile("F:/fake/image.png")
    valid_mime.setUrls([url])
    drag_enter_event = QtGui.QDragEnterEvent(
        QtCore.QPoint(10, 10), QtCore.Qt.CopyAction, valid_mime, QtCore.Qt.NoButton, QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(window, drag_enter_event)
    assert window.drop_overlay.isVisible()
    assert drag_enter_event.isAccepted()

    # 3. Drag leave hides overlay
    drag_leave_event = QtGui.QDragLeaveEvent()
    QtWidgets.QApplication.sendEvent(window, drag_leave_event)
    assert not window.drop_overlay.isVisible()

    # 4. Drop event hides overlay and opens file
    QtWidgets.QApplication.sendEvent(window, drag_enter_event)  # Re-show overlay
    assert window.drop_overlay.isVisible()
    drop_event = QtGui.QDropEvent(QtCore.QPoint(10, 10), QtCore.Qt.CopyAction, valid_mime, QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.sendEvent(window, drop_event)
    assert not window.drop_overlay.isVisible()
    assert open_calls == ["F:\\fake\\image.png"]
    assert drop_event.isAccepted()

def test_main_window_menu_actions_and_shortcuts(monkeypatch, qt_app):
    # Test Exit action
    close_calls = []
    about_calls = []
    open_url_calls = []
    window = UIQtRender.MainWindow()
    monkeypatch.setattr(window, "close", lambda: close_calls.append(True))

    file_menu = window.menuBar().actions()[0].menu()
    exit_action = None
    for action in file_menu.actions():
        if "Exit" in action.text():
            exit_action = action
            break

    assert exit_action is not None
    assert exit_action.shortcut().toString() == "Ctrl+Q"
    exit_action.trigger()
    assert close_calls == [True]

    # Test Open action
    open_calls = []
    monkeypatch.setattr(
        UIQtRender.QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("/fake/path/image.png", "Images (*.png *.jpg *.jpeg *.webp)"),
    )
    monkeypatch.setattr(window, "open_portrait_editor_with_file", lambda path: open_calls.append(path))

    open_action = file_menu.actions()[0]
    assert "Open" in open_action.text()
    assert open_action.shortcut().toString() == "Ctrl+O"

    open_action.trigger()
    assert open_calls == ["/fake/path/image.png"]

    # Test Help > Check for Updates action
    monkeypatch.setattr(
        UIQtRender.QtGui.QDesktopServices,
        "openUrl",
        lambda url: open_url_calls.append(url.toString()),
    )
    help_menu = window.menuBar().actions()[1].menu()
    update_action = help_menu.actions()[0]
    assert "Updates" in update_action.text()
    update_action.trigger()
    assert open_url_calls == [
        "https://github.com/indoctrinatedrecluse/OwlcatPortraitTool/releases"
    ]

    # Test Help > About action
    monkeypatch.setattr(window, "show_about_dialog", lambda: about_calls.append(True))
    about_action = help_menu.actions()[2]
    assert "About" in about_action.text()
    about_action.trigger()
    assert about_calls == [True]


def test_main_window_recent_files_menu(monkeypatch, qt_app, tmp_path):
    # Mock services
    recent_files_list = []
    add_calls = []
    remove_calls = []

    def mock_get_recent():
        return recent_files_list

    def mock_add_recent(path):
        add_calls.append(path)
        if path in recent_files_list:
            recent_files_list.remove(path)
        recent_files_list.insert(0, path)

    def mock_remove_recent(path):
        remove_calls.append(path)
        if path in recent_files_list:
            recent_files_list.remove(path)

    monkeypatch.setattr(UIQtRender, "get_recent_files", mock_get_recent)
    monkeypatch.setattr(UIQtRender, "add_recent_file", mock_add_recent)
    monkeypatch.setattr(UIQtRender, "remove_recent_file", mock_remove_recent)

    # Mock UI dialogs
    warning_messages = []
    monkeypatch.setattr(
        UIQtRender.QtWidgets.QMessageBox,
        "warning",
        lambda *args: warning_messages.append(args[2]),
    )
    monkeypatch.setattr(UIQtRender, "load_image_from_file", lambda path: Image.new("RGBA", (1, 1)))

    # --- Test ---
    window = UIQtRender.MainWindow()
    menu = window.recent_files_menu

    # 1. Initial state: empty
    assert menu.actions()[0].text() == "No recent files"
    assert not menu.actions()[0].isEnabled()

    # 2. Open a file, it gets added
    file1 = tmp_path / "file1.png"
    file1.touch()
    window.open_portrait_editor_with_file(str(file1))
    assert add_calls == [str(file1)]
    assert menu.actions()[0].text() == str(file1)

    # 3. Click a non-existent recent file
    non_existent_file = "F:/non/existent/file.png"
    recent_files_list.insert(0, non_existent_file)
    window.update_recent_files_menu()
    menu.actions()[0].trigger()
    assert len(warning_messages) == 1
    assert "File Not Found" in warning_messages[0]
    assert remove_calls == [non_existent_file]
    assert menu.actions()[0].text() == str(file1)

    # 4. Click an invalid image file
    def mock_load_fail(path):
        raise ValueError("bad format")
    monkeypatch.setattr(UIQtRender, "load_image_from_file", mock_load_fail)
    menu.actions()[0].trigger()
    assert len(warning_messages) == 2
    assert "Invalid Image File" in warning_messages[1]
    assert remove_calls == [non_existent_file, str(file1)]


def test_main_window_clear_recent_files_action_with_confirmation(
    monkeypatch, qt_app, tmp_path
):
    # Mock services
    recent_files_list = []
    clear_calls = []

    def mock_get_recent():
        return recent_files_list

    def mock_add_recent(path):
        if path not in recent_files_list:
            recent_files_list.insert(0, path)

    def mock_clear_recent():
        clear_calls.append(True)
        recent_files_list.clear()

    monkeypatch.setattr(UIQtRender, "get_recent_files", mock_get_recent)
    monkeypatch.setattr(UIQtRender, "add_recent_file", mock_add_recent)
    monkeypatch.setattr(UIQtRender, "clear_recent_files", mock_clear_recent)

    # --- Test ---
    window = UIQtRender.MainWindow()
    clear_action = window.clear_recent_files_action

    # 1. Initial state: empty, action disabled
    assert not clear_action.isEnabled()

    # 2. Add a file, action becomes enabled
    mock_add_recent(str(tmp_path / "file1.png"))
    window.update_recent_files_menu()
    assert clear_action.isEnabled()

    # 3. Trigger clear action but cancel dialog
    monkeypatch.setattr(window, "ask_yes_no", lambda title, message: False)
    clear_action.trigger()
    assert clear_calls == []
    assert clear_action.isEnabled()

    # 4. Trigger clear action and confirm dialog
    monkeypatch.setattr(window, "ask_yes_no", lambda title, message: True)
    clear_action.trigger()
    assert clear_calls == [True]
    assert not clear_action.isEnabled()
