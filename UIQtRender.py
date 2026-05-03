from io import BytesIO
import random
import functools
import string
import sys
from pathlib import Path

import requests
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

from GlobalsService import (
    get_full_length_portrait_size,
    get_next_game_name,
    get_recent_files,
    get_required_portrait_dimensions,
    get_recent_export_folder,
    get_selected_booru,
    get_selected_tab,
    get_window_settings,
    add_recent_file,
    clear_recent_files,
    set_appdata_locallow_folder,
    remove_recent_file,
    set_game_name,
    set_recent_export_folder,
    set_selected_tab,
    set_selected_booru,
    set_window_settings,
    settings,
)
from SearchService import (
    MAX_SEARCH_RESULTS_PER_PAGE,
    get_booru_sites,
    search_portraits_by_tags,
)
from RequestHeaders import IMAGE_REQUEST_HEADERS
from URLService import get_image_from_url, is_valid_url


PORTRAIT_EDITOR_TAB_INDEX = 0
IMAGE_REQUEST_TIMEOUT_SECONDS = 20
MIN_THUMBNAIL_WIDTH = 150
MAX_THUMBNAIL_WIDTH = 220
RESULT_CELL_PADDING = 24
RESULT_CELL_SPACING = 12
MAX_CONCURRENT_PREVIEW_LOADS = 6
MAX_SEARCH_PAGES = 20
MAX_PREVIEW_LOAD_ATTEMPTS = 5
MAX_RECENT_FILES = 10
PREVIEW_REQUEST_TIMEOUT_SECONDS = 8
RESULT_IMAGE_URL_ROLE = QtCore.Qt.UserRole
RESULT_PREVIEW_FAILURE_ROLE = QtCore.Qt.UserRole + 1
SOURCE_LOAD_LOCAL = "local"
SOURCE_LOAD_URL = "url"
LOCAL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
LOCAL_OUTPUT_FOLDER = Path(__file__).resolve().parent / "output"
PORTRAIT_FOLDER_NAME_LENGTH = 16
PORTRAIT_FOLDER_ALPHABET = string.ascii_uppercase + string.digits
APP_CLOSE_CONFIRMATION_TITLE = "Close Owlcat Portrait Tool?"
APP_CLOSE_CONFIRMATION_MESSAGE = "Are you sure you want to close Owlcat Portrait Tool?"
UNSAVED_EDITOR_CONFIRMATION_TITLE = "Leave Portrait Editor?"
UNSAVED_EDITOR_CONFIRMATION_MESSAGE = (
    "You have unsaved portrait changes. Leave the Portrait Editor without exporting?"
)
APP_VERSION = "0.5.3"


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Owlcat Portrait Tool")

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        title_label = QtWidgets.QLabel(f"Owlcat Portrait Tool v{APP_VERSION}")
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        author_label = QtWidgets.QLabel("Author: indoctrinatedrecluse")
        layout.addWidget(author_label)

        github_link = "https://github.com/indoctrinatedrecluse/OwlcatPortraitTool"
        github_label = QtWidgets.QLabel(f'<a href="{github_link}">{github_link}</a>')
        github_label.setOpenExternalLinks(True)
        layout.addWidget(github_label)

        layout.addWidget(QtWidgets.QFrame(self, frameShape=QtWidgets.QFrame.HLine))

        instructions_text = """
        <h4>How to Use</h4>
        <p>This tool helps you create custom portraits for Owlcat Games.</p>
        <ul>
            <li><b>Search Tab:</b> Find images by URL or by searching tags on various image boards. Click a result to open it in the editor.</li>
            <li><b>Portrait Editor Tab:</b> Drag and zoom your selected image to position it within the crop frame. When you're ready, use the export buttons to save the portraits.</li>
            <li><b>Settings Tab:</b> Switch between supported games to use the correct portrait dimensions and save paths for each.</li>
        </ul>
        """
        instructions_label = QtWidgets.QLabel(instructions_text)
        instructions_label.setWordWrap(True)
        instructions_label.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(instructions_label)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)

class PreviewLoaderSignals(QtCore.QObject):
    loaded = QtCore.pyqtSignal(int, int, QtGui.QImage)
    failed = QtCore.pyqtSignal(int, int, str)


class PreviewLoader(QtCore.QRunnable):
    def __init__(self, generation, result_index, result):
        super().__init__()
        self.generation = generation
        self.result_index = result_index
        self.result = result
        self.signals = PreviewLoaderSignals()

    def run(self):
        try:
            image = load_preview_image(self.result)
        except Exception as error:
            self.signals.failed.emit(
                self.generation,
                self.result_index,
                str(error),
            )
            return

        self.signals.loaded.emit(self.generation, self.result_index, image)


class SourceImageLoaderSignals(QtCore.QObject):
    loaded = QtCore.pyqtSignal(int, str, object)
    failed = QtCore.pyqtSignal(int, str, str)


class SourceImageLoader(QtCore.QRunnable):
    def __init__(self, generation, source_kind, source):
        super().__init__()
        self.generation = generation
        self.source_kind = source_kind
        self.source = source
        self.signals = SourceImageLoaderSignals()

    def run(self):
        try:
            image = load_source_image(self.source_kind, self.source)
        except Exception as error:
            self.signals.failed.emit(self.generation, self.source, str(error))
            return

        self.signals.loaded.emit(self.generation, self.source, image)


class MainWindow(QtWidgets.QMainWindow):
    """Main application window with one tab per screen."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Owlcat Portrait Tool {APP_VERSION}")
        window_settings = get_window_settings()
        self.setGeometry(
            window_settings["x"],
            window_settings["y"],
            window_settings["width"],
            window_settings["height"],
        )

        self.setAcceptDrops(True)
        self.setup_drop_overlay()

        self.setup_menu_bar()

        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.setup_portrait_editor_tab()
        self.setup_search_tab()
        self.setup_settings_tab()
        self.original_tab_color = self.tab_widget.tabBar().tabTextColor(0)
        self.update_recent_files_menu()
        self.previous_tab_index = self.tab_widget.currentIndex()
        self.reverting_tab_change = False
        self.tab_widget.currentChanged.connect(self.handle_tab_changed)
        selected_tab = min(get_selected_tab(), self.tab_widget.count() - 1)
        self.tab_widget.setCurrentIndex(selected_tab)
        self.previous_tab_index = selected_tab

    def setup_portrait_editor_tab(self):
        self.portrait_editor_tab = PortraitEditorTab(self)
        self.tab_widget.addTab(self.portrait_editor_tab, "Portrait Editor")

    def setup_search_tab(self):
        self.search_tab = SearchTab(self)
        self.tab_widget.addTab(self.search_tab, "Search")

    def setup_settings_tab(self):
        self.settings_tab = SettingsTab()
        self.tab_widget.addTab(self.settings_tab, "Settings")

    def show_portrait_editor_tab(self):
        self.tab_widget.setCurrentIndex(PORTRAIT_EDITOR_TAB_INDEX)

    def open_portrait_editor_with_url(self, image_url):
        self.portrait_editor_tab.set_source_url(image_url)
        self.show_portrait_editor_tab()

    def open_portrait_editor_with_file(self, image_path):
        add_recent_file(image_path)
        self.update_recent_files_menu()
        self.portrait_editor_tab.set_source_file(image_path)
        self.show_portrait_editor_tab()

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    def check_for_updates(self):
        releases_url = "https://github.com/indoctrinatedrecluse/OwlcatPortraitTool/releases"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(releases_url))

    def open_recent_file(self, file_path):
        path = Path(file_path)
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "File Not Found",
                f"The file could not be found and will be removed from the recent files list:\n{file_path}",
            )
            remove_recent_file(file_path)
            self.update_recent_files_menu()
            return

        try:
            load_image_from_file(file_path)
        except ValueError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Image File",
                f"The file is not a valid image and will be removed from the recent files list:\n{file_path}\n\nReason: {error}",
            )
            remove_recent_file(file_path)
            self.update_recent_files_menu()
            return

        self.open_portrait_editor_with_file(file_path)

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        recent_files = get_recent_files()

        self.clear_recent_files_action.setEnabled(bool(recent_files))

        if not recent_files:
            action = self.recent_files_menu.addAction("No recent files")
            action.setEnabled(False)
            return

        for file_path in recent_files:
            action = QtWidgets.QAction(file_path, self)
            action.triggered.connect(
                functools.partial(self.open_recent_file, file_path)
            )
            self.recent_files_menu.addAction(action)

    def clear_recent_files(self):
        if self.ask_yes_no(
            "Clear Recent Files?",
            "Are you sure you want to clear the recent files list?",
        ):
            clear_recent_files()
            self.update_recent_files_menu()

    def update_portrait_editor_tab_title(self):
        is_dirty = self.portrait_editor_tab.has_unsaved_changes
        base_title = "Portrait Editor"
        tab_bar = self.tab_widget.tabBar()

        if is_dirty:
            tab_bar.setTabText(PORTRAIT_EDITOR_TAB_INDEX, f"{base_title} *")
            tab_bar.setTabTextColor(PORTRAIT_EDITOR_TAB_INDEX, QtGui.QColor("orange"))
        else:
            tab_bar.setTabText(PORTRAIT_EDITOR_TAB_INDEX, base_title)
            tab_bar.setTabTextColor(PORTRAIT_EDITOR_TAB_INDEX, self.original_tab_color)

    def setup_drop_overlay(self):
        self.drop_overlay = QtWidgets.QLabel("Drop image here", self)
        self.drop_overlay.setAlignment(QtCore.Qt.AlignCenter)
        self.drop_overlay.setStyleSheet(
            """
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: 2px dashed white;
            }
            """
        )
        self.drop_overlay.hide()

    def setup_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        open_action = QtWidgets.QAction("&Open Image...", self)
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self.open_local_image_dialog)
        file_menu.addAction(open_action)

        self.recent_files_menu = file_menu.addMenu("Recent Files")

        self.clear_recent_files_action = file_menu.addAction("Clear Recent Files")
        self.clear_recent_files_action.setEnabled(False)
        self.clear_recent_files_action.triggered.connect(self.clear_recent_files)

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("&Help")

        check_for_updates_action = QtWidgets.QAction("Check for &Updates...", self)
        check_for_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(check_for_updates_action)

        help_menu.addSeparator()

        about_action = QtWidgets.QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def open_local_image_dialog(self):
        selected_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Portrait Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if selected_file:
            self.open_portrait_editor_with_file(selected_file)

    def handle_tab_changed(self, tab_index):
        if self.reverting_tab_change:
            return

        set_selected_tab(tab_index)
        previous_tab_index = self.previous_tab_index
        self.previous_tab_index = tab_index

        if previous_tab_index != PORTRAIT_EDITOR_TAB_INDEX:
            return

        if tab_index == PORTRAIT_EDITOR_TAB_INDEX:
            return

        if not self.portrait_editor_tab.has_unsaved_changes:
            return

        if self.confirm_leave_portrait_editor():
            return

        self.reverting_tab_change = True
        self.tab_widget.setCurrentIndex(previous_tab_index)
        self.previous_tab_index = previous_tab_index
        set_selected_tab(previous_tab_index)
        self.reverting_tab_change = False

    def confirm_leave_portrait_editor(self):
        return self.ask_yes_no(
            UNSAVED_EDITOR_CONFIRMATION_TITLE,
            UNSAVED_EDITOR_CONFIRMATION_MESSAGE,
        )

    def confirm_close_application(self):
        return self.ask_yes_no(
            APP_CLOSE_CONFIRMATION_TITLE,
            APP_CLOSE_CONFIRMATION_MESSAGE,
        )

    def ensure_current_game_path_exists(self):
        return self.settings_tab.ensure_current_game_path_exists()

    def ask_yes_no(self, title, message):
        answer = QtWidgets.QMessageBox.question(
            self,
            title,
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return answer == QtWidgets.QMessageBox.Yes

    def closeEvent(self, event):
        if self.portrait_editor_tab.has_unsaved_changes:
            if not self.confirm_leave_portrait_editor():
                event.ignore()
                return
        elif not self.confirm_close_application():
            event.ignore()
            return

        geometry = self.geometry()
        set_window_settings(
            geometry.x(),
            geometry.y(),
            geometry.width(),
            geometry.height(),
        )
        set_selected_tab(self.tab_widget.currentIndex())
        super().closeEvent(event)


class PortraitEditorTab(QtWidgets.QWidget):
    """Screen 1: portrait loading and editing."""

    def __init__(self, main_window):
        super().__init__()
        self.setAcceptDrops(True)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.main_window = main_window
        self.source_url = None
        self.source_file = None
        self.source_image = None
        self.has_unsaved_changes = False
        self.source_generation = 0
        self.source_thread_pool = QtCore.QThreadPool(self)
        self.source_thread_pool.setMaxThreadCount(1)
        self.last_local_export_folder = get_recent_export_folder("local")
        self.last_game_export_folder = get_recent_export_folder("game")

        self.source_label = QtWidgets.QLabel("No portrait selected")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.source_label)

        load_button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(load_button_layout)

        self.load_file_button = QtWidgets.QPushButton("Load Local Image...")
        self.load_file_button.clicked.connect(self.main_window.open_local_image_dialog)
        load_button_layout.addWidget(self.load_file_button)

        self.crop_canvas = PortraitCropCanvas()
        self.crop_canvas.cropChanged.connect(self.mark_unsaved_changes)
        self.crop_canvas.cropChanged.connect(self.update_export_previews)
        layout.addWidget(self.crop_canvas, stretch=1)

        zoom_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(zoom_layout)

        self.zoom_out_button = QtWidgets.QPushButton("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_out_button.setEnabled(False)
        zoom_layout.addWidget(self.zoom_out_button)

        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.zoom_slider.setRange(100, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setEnabled(False)
        self.zoom_slider.valueChanged.connect(self.apply_zoom_slider_value)
        zoom_layout.addWidget(self.zoom_slider)

        self.zoom_in_button = QtWidgets.QPushButton("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_in_button.setEnabled(False)
        zoom_layout.addWidget(self.zoom_in_button)

        self.preview_group = QtWidgets.QGroupBox("Export Preview")
        preview_layout = QtWidgets.QHBoxLayout()
        self.preview_group.setLayout(preview_layout)
        layout.addWidget(self.preview_group)
        self.preview_labels = {}
        for portrait_size in get_required_portrait_dimensions():
            preview_label = QtWidgets.QLabel(portrait_size.name)
            preview_label.setAlignment(QtCore.Qt.AlignCenter)
            preview_label.setMinimumSize(96, 120)
            preview_label.setFrameShape(QtWidgets.QFrame.Box)
            preview_layout.addWidget(preview_label)
            self.preview_labels[portrait_size.name] = preview_label

        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(button_layout)

        self.export_local_button = QtWidgets.QPushButton("Export To Local Output")
        self.export_local_button.clicked.connect(self.export_local)
        self.export_local_button.setEnabled(False)
        button_layout.addWidget(self.export_local_button)

        self.export_game_button = QtWidgets.QPushButton("Export To AppData/Portraits")
        self.export_game_button.clicked.connect(self.export_to_game)
        self.export_game_button.setEnabled(False)
        button_layout.addWidget(self.export_game_button)

        self.open_local_folder_button = QtWidgets.QPushButton("Open Local Folder")
        self.open_local_folder_button.clicked.connect(self.open_last_local_export_folder)
        self.open_local_folder_button.setEnabled(self.last_local_export_folder.exists())
        button_layout.addWidget(self.open_local_folder_button)

        self.open_game_folder_button = QtWidgets.QPushButton("Open AppData Folder")
        self.open_game_folder_button.clicked.connect(self.open_last_game_export_folder)
        self.open_game_folder_button.setEnabled(self.last_game_export_folder.exists())
        button_layout.addWidget(self.open_game_folder_button)

        export_path_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(export_path_layout)

        self.export_path_field = QtWidgets.QLineEdit()
        self.export_path_field.setReadOnly(True)
        self.export_path_field.setPlaceholderText("Last export path will be shown here")
        export_path_layout.addWidget(self.export_path_field, stretch=1)

        self.copy_path_button = QtWidgets.QPushButton("Copy")
        self.copy_path_button.clicked.connect(self.copy_export_path)
        self.copy_path_button.setEnabled(False)
        export_path_layout.addWidget(self.copy_path_button)

        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_source_url(self, image_url):
        self.load_source(SOURCE_LOAD_URL, image_url)

    def set_source_file(self, image_path):
        self.load_source(SOURCE_LOAD_LOCAL, str(image_path))

    def load_source(self, source_kind, source):
        self.has_unsaved_changes = False
        self.source_url = source if source_kind == SOURCE_LOAD_URL else None
        self.source_file = Path(source) if source_kind == SOURCE_LOAD_LOCAL else None
        self.source_generation += 1
        self.source_thread_pool.clear()

        source_label = "URL" if source_kind == SOURCE_LOAD_URL else "File"
        self.source_label.setText(f"Selected portrait {source_label.lower()}:\n{source}")
        self.export_path_field.clear()
        self.copy_path_button.setEnabled(False)
        self.status_label.setText("Loading image...")
        self.set_editor_actions_enabled(False)
        self.clear_export_previews()

        worker = SourceImageLoader(self.source_generation, source_kind, source)
        worker.signals.loaded.connect(self.source_loaded)
        worker.signals.failed.connect(self.source_failed)
        self.source_thread_pool.start(worker)

    def source_loaded(self, generation, source, image):
        if generation != self.source_generation:
            return

        self.source_image = image.convert("RGBA")
        self.crop_canvas.set_image(self.source_image)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(100)
        self.zoom_slider.blockSignals(False)
        self.set_editor_actions_enabled(True)
        self.update_export_previews()
        self.status_label.setText("Drag the image to position it inside the crop outline.")

    def source_failed(self, generation, source, error):
        if generation != self.source_generation:
            return

        self.source_image = None
        self.crop_canvas.clear_image()
        self.clear_export_previews()
        self.set_editor_actions_enabled(False)
        self.status_label.setText(format_image_load_error(source, error))

    def set_editor_actions_enabled(self, enabled):
        self.export_local_button.setEnabled(enabled)
        self.export_game_button.setEnabled(enabled)
        self.zoom_slider.setEnabled(enabled)
        self.zoom_in_button.setEnabled(enabled)
        self.zoom_out_button.setEnabled(enabled)

    def set_dirty_state(self, is_dirty):
        """Set the unsaved changes state and update the UI indicator."""
        if self.has_unsaved_changes == is_dirty:
            return

        self.has_unsaved_changes = is_dirty
        self.main_window.update_portrait_editor_tab_title()

    def mark_unsaved_changes(self):
        if self.source_image is not None:
            self.set_dirty_state(True)

    def export_local(self):
        output_folder = self.export_portrait_set(LOCAL_OUTPUT_FOLDER)
        if output_folder:
            self.last_local_export_folder = output_folder
            set_recent_export_folder("local", output_folder)
            self.open_local_folder_button.setEnabled(True)

    def export_to_game(self):
        if not self.main_window.ensure_current_game_path_exists():
            return

        output_folder = self.export_portrait_set(settings.output_folder)
        if output_folder:
            self.last_game_export_folder = output_folder
            set_recent_export_folder("game", output_folder)
            self.open_game_folder_button.setEnabled(True)

    def export_portrait_set(self, output_root):
        if self.source_image is None:
            self.status_label.setText("Load an image before exporting.")
            return None

        try:
            output_folder = create_unique_portrait_folder(output_root)
        except OSError as error:
            self.status_label.setText(f"Could not create export folder: {error}")
            return None

        cropped_image = self.crop_canvas.get_cropped_image()
        for portrait_size in get_required_portrait_dimensions():
            output_image = cropped_image.resize(
                (portrait_size.width, portrait_size.height),
                Image.Resampling.LANCZOS,
            )
            output_image.save(output_folder / portrait_size.name)

        self.set_dirty_state(False)
        self.export_path_field.setText(str(output_folder))
        self.copy_path_button.setEnabled(True)
        self.status_label.setText("Export successful.")
        return output_folder

    def copy_export_path(self):
        path_to_copy = self.export_path_field.text()
        if not path_to_copy:
            return

        QtWidgets.QApplication.clipboard().setText(path_to_copy)
        self.status_label.setText("Copied path to clipboard.")

    def load_pil_image(self, image, source_description):
        self.set_dirty_state(False)
        self.source_url = None
        self.source_file = None
        self.source_generation += 1
        self.source_thread_pool.clear()

        self.source_label.setText(f"Selected portrait source:\n{source_description}")
        self.export_path_field.clear()
        self.copy_path_button.setEnabled(False)

        self.source_loaded(
            self.source_generation, source_description, image.copy()
        )

    def update_export_previews(self):
        if self.source_image is None:
            self.clear_export_previews()
            return

        try:
            cropped_image = self.crop_canvas.get_cropped_image()
        except ValueError:
            self.clear_export_previews()
            return

        for portrait_size in get_required_portrait_dimensions():
            preview_label = self.preview_labels.get(portrait_size.name)
            if preview_label is None:
                continue

            preview_image = cropped_image.resize(
                (portrait_size.width, portrait_size.height),
                Image.Resampling.LANCZOS,
            )
            pixmap = image_to_pixmap(preview_image).scaled(
                preview_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            preview_label.setText("")
            preview_label.setPixmap(pixmap)

    def clear_export_previews(self):
        for portrait_size in get_required_portrait_dimensions():
            preview_label = self.preview_labels.get(portrait_size.name)
            if preview_label:
                preview_label.clear()
                preview_label.setText(portrait_size.name)

    def zoom_in(self):
        self.zoom_slider.setValue(min(self.zoom_slider.maximum(), self.zoom_slider.value() + 10))

    def zoom_out(self):
        self.zoom_slider.setValue(max(self.zoom_slider.minimum(), self.zoom_slider.value() - 10))

    def apply_zoom_slider_value(self, value):
        if self.source_image is None:
            return

        minimum_scale = self.crop_canvas.minimum_cover_scale()
        self.crop_canvas.set_zoom_scale(minimum_scale * (value / 100))
        self.mark_unsaved_changes()
        self.update_export_previews()

    def open_last_local_export_folder(self):
        self.open_folder(self.last_local_export_folder)

    def open_last_game_export_folder(self):
        self.open_folder(self.last_game_export_folder)

    def open_folder(self, folder):
        if not folder:
            return False

        folder = Path(folder)
        if not folder.exists():
            self.status_label.setText(f"Folder does not exist:\n{folder}")
            return False

        return QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(folder))
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_export_previews()

    def closeEvent(self, event):
        self.source_thread_pool.clear()
        self.source_thread_pool.waitForDone(100)
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_P and event.modifiers() == QtCore.Qt.ControlModifier:
            clipboard = QtWidgets.QApplication.clipboard()
            mime_data = clipboard.mimeData()
            if mime_data.hasImage():
                q_image = clipboard.image()
                if not q_image.isNull():
                    buffer = QtCore.QBuffer()
                    buffer.open(QtCore.QBuffer.ReadWrite)
                    q_image.save(buffer, "PNG")
                    pil_image = Image.open(BytesIO(buffer.data()))
                    buffer.close()

                    self.load_pil_image(pil_image, "Pasted from clipboard")
                    event.accept()
                    return

        super().keyPressEvent(event)

class PortraitCropCanvas(QtWidgets.QWidget):
    """Draggable image preview with a fixed Pathfinder full-length crop frame."""

    cropChanged = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 420)
        self.setMouseTracking(True)

        self.source_image = None
        self.source_pixmap = None
        self.image_offset = QtCore.QPointF(0, 0)
        self.image_scale = 1.0
        self.drag_start_pos = None
        self.drag_start_offset = None

    def set_image(self, image):
        self.source_image = image.copy()
        self.source_pixmap = image_to_pixmap(self.source_image)
        self.fit_image_to_crop()
        self.update()

    def clear_image(self):
        self.source_image = None
        self.source_pixmap = None
        self.update()

    def fit_image_to_crop(self):
        if self.source_image is None:
            return

        crop_rect = self.get_crop_rect()
        self.image_scale = max(
            crop_rect.width() / self.source_image.width,
            crop_rect.height() / self.source_image.height,
        )
        image_width = self.source_image.width * self.image_scale
        image_height = self.source_image.height * self.image_scale
        self.image_offset = QtCore.QPointF(
            crop_rect.center().x() - image_width / 2,
            crop_rect.center().y() - image_height / 2,
        )
        self.constrain_image_to_crop()

    def minimum_cover_scale(self):
        if self.source_image is None:
            return 1.0

        crop_rect = self.get_crop_rect()
        return max(
            crop_rect.width() / self.source_image.width,
            crop_rect.height() / self.source_image.height,
        )

    def set_zoom_scale(self, image_scale):
        if self.source_image is None:
            return

        old_rect = self.get_image_rect()
        anchor = self.get_crop_rect().center()
        if old_rect.width() > 0 and old_rect.height() > 0:
            relative_x = (anchor.x() - old_rect.left()) / old_rect.width()
            relative_y = (anchor.y() - old_rect.top()) / old_rect.height()
        else:
            relative_x = 0.5
            relative_y = 0.5

        self.image_scale = max(self.minimum_cover_scale(), image_scale)
        new_width = self.source_image.width * self.image_scale
        new_height = self.source_image.height * self.image_scale
        self.image_offset = QtCore.QPointF(
            anchor.x() - new_width * relative_x,
            anchor.y() - new_height * relative_y,
        )
        self.constrain_image_to_crop()
        self.update()

    def get_crop_rect(self):
        portrait_size = get_full_length_portrait_size()
        margin = 32
        available_width = max(self.width() - margin * 2, 1)
        available_height = max(self.height() - margin * 2, 1)
        crop_aspect = portrait_size.width / portrait_size.height

        crop_width = available_width
        crop_height = crop_width / crop_aspect
        if crop_height > available_height:
            crop_height = available_height
            crop_width = crop_height * crop_aspect

        left = (self.width() - crop_width) / 2
        top = (self.height() - crop_height) / 2
        return QtCore.QRectF(left, top, crop_width, crop_height)

    def get_image_rect(self):
        if self.source_image is None:
            return QtCore.QRectF()

        return QtCore.QRectF(
            self.image_offset.x(),
            self.image_offset.y(),
            self.source_image.width * self.image_scale,
            self.source_image.height * self.image_scale,
        )

    def constrain_image_to_crop(self):
        if self.source_image is None:
            return

        crop_rect = self.get_crop_rect()
        image_rect = self.get_image_rect()
        offset_x = self.image_offset.x()
        offset_y = self.image_offset.y()

        if image_rect.width() <= crop_rect.width():
            offset_x = crop_rect.center().x() - image_rect.width() / 2
        else:
            if image_rect.left() > crop_rect.left():
                offset_x = crop_rect.left()
            if image_rect.right() < crop_rect.right():
                offset_x = crop_rect.right() - image_rect.width()

        if image_rect.height() <= crop_rect.height():
            offset_y = crop_rect.center().y() - image_rect.height() / 2
        else:
            if image_rect.top() > crop_rect.top():
                offset_y = crop_rect.top()
            if image_rect.bottom() < crop_rect.bottom():
                offset_y = crop_rect.bottom() - image_rect.height()

        self.image_offset = QtCore.QPointF(offset_x, offset_y)

    def get_cropped_image(self):
        if self.source_image is None:
            raise ValueError("No image loaded.")

        crop_rect = self.get_crop_rect()
        left = int((crop_rect.left() - self.image_offset.x()) / self.image_scale)
        top = int((crop_rect.top() - self.image_offset.y()) / self.image_scale)
        right = int((crop_rect.right() - self.image_offset.x()) / self.image_scale)
        bottom = int((crop_rect.bottom() - self.image_offset.y()) / self.image_scale)

        left = max(0, min(left, self.source_image.width - 1))
        top = max(0, min(top, self.source_image.height - 1))
        right = max(left + 1, min(right, self.source_image.width))
        bottom = max(top + 1, min(bottom, self.source_image.height))

        full_size = get_full_length_portrait_size()
        return self.source_image.crop((left, top, right, bottom)).resize(
            (full_size.width, full_size.height),
            Image.Resampling.LANCZOS,
        )

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(35, 35, 35))

        if self.source_pixmap is None:
            painter.setPen(QtGui.QColor(210, 210, 210))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "Select an image to edit")
            return

        image_rect = self.get_image_rect()
        painter.drawPixmap(
            image_rect,
            self.source_pixmap,
            QtCore.QRectF(self.source_pixmap.rect()),
        )

        crop_rect = self.get_crop_rect()
        overlay_color = QtGui.QColor(0, 0, 0, 130)
        painter.fillRect(QtCore.QRectF(0, 0, self.width(), crop_rect.top()), overlay_color)
        painter.fillRect(
            QtCore.QRectF(0, crop_rect.bottom(), self.width(), self.height() - crop_rect.bottom()),
            overlay_color,
        )
        painter.fillRect(
            QtCore.QRectF(0, crop_rect.top(), crop_rect.left(), crop_rect.height()),
            overlay_color,
        )
        painter.fillRect(
            QtCore.QRectF(crop_rect.right(), crop_rect.top(), self.width() - crop_rect.right(), crop_rect.height()),
            overlay_color,
        )

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        painter.drawRect(crop_rect)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.source_image is not None:
            self.drag_start_pos = event.pos()
            self.drag_start_offset = QtCore.QPointF(self.image_offset)
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is None:
            return

        delta = event.pos() - self.drag_start_pos
        self.image_offset = self.drag_start_offset + QtCore.QPointF(delta)
        self.constrain_image_to_crop()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            crop_changed = (
                self.source_image is not None
                and self.drag_start_offset is not None
                and self.image_offset != self.drag_start_offset
            )
            self.drag_start_pos = None
            self.drag_start_offset = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            if crop_changed:
                self.cropChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image_to_crop()


def image_to_pixmap(image):
    image = image.convert("RGBA")
    image_data = image.tobytes("raw", "RGBA")
    qt_image = QtGui.QImage(
        image_data,
        image.width,
        image.height,
        QtGui.QImage.Format_RGBA8888,
    )
    return QtGui.QPixmap.fromImage(qt_image.copy())


def load_source_image(source_kind, source):
    if source_kind == SOURCE_LOAD_URL:
        return get_image_from_url(source).convert("RGBA")

    if source_kind == SOURCE_LOAD_LOCAL:
        return load_image_from_file(source).convert("RGBA")

    raise ValueError("Unsupported image source.")


def load_image_from_file(image_path):
    image_path = Path(image_path)
    if image_path.suffix.lower() not in LOCAL_IMAGE_EXTENSIONS:
        raise ValueError("Select a supported image file: PNG, JPG, JPEG, or WEBP.")

    try:
        with Image.open(image_path) as image:
            image.verify()
        return Image.open(image_path)
    except OSError as error:
        raise ValueError(f"Could not open image file: {error}") from error


def format_image_load_error(source, error):
    return (
        "Could not load image.\n"
        f"Source: {source}\n"
        f"Reason: {error}\n"
        "Try another image, check the file path, or use a different host."
    )


def load_preview_image(result):
    preview_url = result.preview_url or result.image_url
    last_error = None

    for _ in range(MAX_PREVIEW_LOAD_ATTEMPTS):
        try:
            response = requests.get(
                preview_url,
                headers=IMAGE_REQUEST_HEADERS,
                timeout=PREVIEW_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            image.thumbnail((MAX_THUMBNAIL_WIDTH, MAX_THUMBNAIL_WIDTH * 2))
            image = image.convert("RGBA")

            image_data = image.tobytes("raw", "RGBA")
            qt_image = QtGui.QImage(
                image_data,
                image.width,
                image.height,
                QtGui.QImage.Format_RGBA8888,
            )
            return qt_image.copy()
        except Exception as error:
            last_error = error

    raise RuntimeError(
        f"Could not load preview after {MAX_PREVIEW_LOAD_ATTEMPTS} attempts: "
        f"{last_error}"
    )


def generate_portrait_folder_name():
    return "".join(
        random.SystemRandom().choice(PORTRAIT_FOLDER_ALPHABET)
        for _ in range(PORTRAIT_FOLDER_NAME_LENGTH)
    )


def create_unique_portrait_folder(output_root):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    while True:
        output_folder = output_root / generate_portrait_folder_name()
        try:
            output_folder.mkdir()
            return output_folder
        except FileExistsError:
            continue


class SearchTab(QtWidgets.QWidget):
    """Screen 2: URL input or tag search with results below."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.form_layout = QtWidgets.QFormLayout()
        layout.addLayout(self.form_layout)

        self.input_switch = QtWidgets.QCheckBox("Search by URL")
        self.input_switch.setChecked(True)
        self.input_switch.toggled.connect(self.update_input_mode)
        self.form_layout.addRow(self.input_switch)

        self.booru_sites = get_booru_sites()
        self.booru_selector = QtWidgets.QComboBox()
        self.booru_selector.addItems(self.booru_sites)
        last_selected_booru = get_selected_booru()
        if last_selected_booru in self.booru_sites:
            self.booru_selector.setCurrentText(last_selected_booru)
        self.booru_selector.currentTextChanged.connect(set_selected_booru)
        self.form_layout.addRow("Booru Site", self.booru_selector)

        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Enter URL or tags...")
        self.form_layout.addRow("Search", self.search_bar)

        search_actions_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(search_actions_layout)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.process_search)
        search_actions_layout.addWidget(self.search_button)

        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search)
        search_actions_layout.addWidget(self.clear_button)

        self.pagination_widget = QtWidgets.QWidget()
        pagination_layout = QtWidgets.QHBoxLayout(self.pagination_widget)
        pagination_layout.setContentsMargins(0, 5, 0, 0)
        self.prev_button = QtWidgets.QPushButton("<< Previous")
        self.prev_button.clicked.connect(self.go_to_prev_page)
        self.page_label = QtWidgets.QLabel(f"Page 1 / {MAX_SEARCH_PAGES}")
        self.page_label.setAlignment(QtCore.Qt.AlignCenter)
        self.next_button = QtWidgets.QPushButton("Next >>")
        self.next_button.clicked.connect(self.go_to_next_page)
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_button)
        layout.addWidget(self.pagination_widget)

        self.results_list = QtWidgets.QListWidget()
        self.results_list.setViewMode(QtWidgets.QListView.IconMode)
        self.results_list.setFlow(QtWidgets.QListView.LeftToRight)
        self.results_list.setWrapping(True)
        self.results_list.setResizeMode(QtWidgets.QListView.Adjust)
        self.results_list.setMovement(QtWidgets.QListView.Static)
        self.results_list.setSpacing(RESULT_CELL_SPACING)
        self.results_list.itemClicked.connect(self.open_selected_result)
        layout.addWidget(self.results_list)

        self.image_result_widgets = []
        self.preview_thread_pool = QtCore.QThreadPool(self)
        self.preview_thread_pool.setMaxThreadCount(MAX_CONCURRENT_PREVIEW_LOADS)
        self.preview_generation = 0
        self.current_page = 1
        self.current_tags = []
        self.last_result_count = 0
        self.pagination_widget.hide()
        self.update_input_mode(self.input_switch.isChecked())

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.execute_tag_search()

    def go_to_next_page(self):
        if self.current_page < MAX_SEARCH_PAGES:
            self.current_page += 1
            self.execute_tag_search()

    def update_input_mode(self, is_url_mode):
        self.booru_selector.setVisible(not is_url_mode)
        booru_label = self.form_layout.labelForField(self.booru_selector)
        if booru_label:
            booru_label.setVisible(not is_url_mode)

        if is_url_mode:
            self.search_bar.setPlaceholderText("Enter image URL...")
        else:
            self.search_bar.setPlaceholderText("Enter tags, comma-separated...")

    def get_search_input(self):
        text = self.search_bar.text().strip()
        if self.input_switch.isChecked():
            return text

        return [tag.strip() for tag in text.split(",") if tag.strip()]

    def process_search(self):
        search_input = self.get_search_input()

        if not search_input:
            self.results_list.clear()
            self.results_list.addItem("Enter a URL or at least one tag.")
            self.pagination_widget.hide()
            return

        if self.input_switch.isChecked():
            self.pagination_widget.hide()
            self.handle_url_input(search_input)
            return

        # This is a new tag search
        self.current_tags = search_input
        self.current_page = 1
        self.execute_tag_search()

    def clear_search(self):
        """Clear the search input and results list."""
        self.search_bar.clear()
        self.cancel_preview_loads()
        self.image_result_widgets = []
        self.results_list.clear()
        self.current_page = 1
        self.current_tags = []
        self.pagination_widget.hide()

    def cancel_preview_loads(self):
        self.preview_generation += 1
        self.preview_thread_pool.clear()

    def handle_url_input(self, url):
        if not is_valid_url(url):
            self.results_list.addItem("Enter a valid HTTP or HTTPS image URL.")
            return

        self.main_window.open_portrait_editor_with_url(url)

    def open_selected_result(self, item):
        preview_failure = item.data(RESULT_PREVIEW_FAILURE_ROLE)
        if preview_failure:
            self.show_preview_failure_message(preview_failure)
            return

        image_url = item.data(RESULT_IMAGE_URL_ROLE)
        if image_url:
            self.main_window.open_portrait_editor_with_url(image_url)

    def show_preview_failure_message(self, message):
        QtWidgets.QMessageBox.warning(
            self,
            "Preview Failed",
            f"This preview could not be loaded.\n\n{message}",
        )

    def execute_tag_search(self):
        self.cancel_preview_loads()
        self.image_result_widgets = []
        self.results_list.clear()
        self.results_list.addItem("Searching...")
        QtWidgets.QApplication.processEvents()

        booru_name = self.booru_selector.currentText()

        try:
            results = search_portraits_by_tags(
                self.current_tags, booru_name, page=self.current_page
            )
        except Exception as error:
            self.results_list.clear()
            self.results_list.addItem(f"Search failed: {error}")
            self.pagination_widget.hide()
            return

        self.last_result_count = len(results)
        self.page_label.setText(f"Page {self.current_page} / {MAX_SEARCH_PAGES}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(
            self.current_page < MAX_SEARCH_PAGES
            and self.last_result_count == MAX_SEARCH_RESULTS_PER_PAGE
        )
        self.pagination_widget.show()

        self.results_list.clear()
        if not results:
            self.results_list.addItem("No results found.")
            return

        self.update_results_grid_size()

        for result_index, result in enumerate(results):
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(self.results_list.gridSize())
            item.setData(RESULT_IMAGE_URL_ROLE, result.image_url)
            self.results_list.addItem(item)

            image_label = QtWidgets.QLabel()
            image_label.setAlignment(QtCore.Qt.AlignCenter)
            image_label.setCursor(QtCore.Qt.PointingHandCursor)
            image_label.setToolTip(self.format_result_tooltip(result))
            image_label.setText("Loading...")
            self.results_list.setItemWidget(item, image_label)
            self.image_result_widgets.append((item, image_label, None))

            worker = PreviewLoader(self.preview_generation, result_index, result)
            worker.signals.loaded.connect(self.preview_loaded)
            worker.signals.failed.connect(self.preview_failed)
            self.preview_thread_pool.start(worker)

    def preview_loaded(self, generation, result_index, image):
        if generation != self.preview_generation:
            return

        if result_index >= len(self.image_result_widgets):
            return

        item, image_label, _ = self.image_result_widgets[result_index]
        pixmap = QtGui.QPixmap.fromImage(image)
        self.image_result_widgets[result_index] = (item, image_label, pixmap)
        item.setData(RESULT_PREVIEW_FAILURE_ROLE, None)
        image_label.setText("")
        self.update_result_image(image_label, pixmap)

    def preview_failed(self, generation, result_index, error):
        if generation != self.preview_generation:
            return

        if result_index >= len(self.image_result_widgets):
            return

        item, image_label, _ = self.image_result_widgets[result_index]
        item.setData(RESULT_PREVIEW_FAILURE_ROLE, error)
        image_label.clear()
        image_label.setText("Preview failed")
        image_label.setToolTip(
            f"{image_label.toolTip()}\nPreview failed after "
            f"{MAX_PREVIEW_LOAD_ATTEMPTS} attempts: {error}"
        )

    def format_result_tooltip(self, result):
        if result.width and result.height:
            return f"{result.image_url}\n{result.width} x {result.height}"

        return result.image_url

    def update_results_grid_size(self):
        viewport_width = max(self.results_list.viewport().width(), MAX_THUMBNAIL_WIDTH)
        columns = max(
            1,
            viewport_width // (MAX_THUMBNAIL_WIDTH + RESULT_CELL_PADDING + RESULT_CELL_SPACING),
        )
        thumbnail_width = min(
            MAX_THUMBNAIL_WIDTH,
            max(
                MIN_THUMBNAIL_WIDTH,
                (
                    viewport_width
                    - (RESULT_CELL_SPACING * max(columns - 1, 0))
                    - RESULT_CELL_PADDING
                )
                // columns,
            ),
        )
        thumbnail_height = int(
            thumbnail_width
            * get_full_length_portrait_size().height
            / get_full_length_portrait_size().width
        )
        cell_size = QtCore.QSize(
            thumbnail_width + RESULT_CELL_PADDING,
            thumbnail_height + RESULT_CELL_PADDING,
        )

        self.results_list.setIconSize(QtCore.QSize(thumbnail_width, thumbnail_height))
        self.results_list.setGridSize(cell_size)

        for item, _, _ in self.image_result_widgets:
            item.setSizeHint(cell_size)

    def update_result_images(self):
        for _, image_label, pixmap in self.image_result_widgets:
            if pixmap is None:
                continue

            self.update_result_image(image_label, pixmap)

    def update_result_image(self, image_label, pixmap):
        icon_size = self.results_list.iconSize()
        if pixmap is None:
            return

        scaled_pixmap = pixmap.scaled(
            icon_size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "results_list"):
            self.update_results_grid_size()
            self.update_result_images()

    def closeEvent(self, event):
        self.cancel_preview_loads()
        self.preview_thread_pool.waitForDone(100)
        super().closeEvent(event)


class SettingsTab(QtWidgets.QWidget):
    """Screen 3: application settings."""

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)

        self.target_game_button = QtWidgets.QPushButton()
        self.target_game_button.clicked.connect(self.switch_target_game)
        layout.addRow("Target Game", self.target_game_button)

        self.appdata_path_label = QtWidgets.QLabel()
        self.appdata_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.appdata_path_label.setWordWrap(True)
        layout.addRow("AppData Path", self.appdata_path_label)

        self.portraits_path_label = QtWidgets.QLabel()
        self.portraits_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.portraits_path_label.setWordWrap(True)
        layout.addRow("Portraits Path", self.portraits_path_label)

        self.choose_appdata_button = QtWidgets.QPushButton("Set AppData Path...")
        self.choose_appdata_button.clicked.connect(self.choose_appdata_path)
        layout.addRow(self.choose_appdata_button)

        self.refresh_path_labels()

    def switch_target_game(self):
        self.change_game(get_next_game_name(), validate_path=True)

    def change_game(self, game_name, validate_path=False):
        set_game_name(game_name)
        self.refresh_path_labels()
        if validate_path:
            self.ensure_current_game_path_exists()

    def ensure_current_game_path_exists(self):
        if settings.appdata_locallow_folder.exists():
            return True

        QtWidgets.QMessageBox.warning(
            self,
            "Game Folder Not Found",
            "The saved AppData folder for this game could not be found. "
            "Please select the correct game folder.",
        )
        return self.choose_appdata_path()

    def choose_appdata_path(self):
        selected_folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Game AppData Folder",
            str(settings.appdata_locallow_folder),
        )

        if not selected_folder:
            return False

        set_appdata_locallow_folder(selected_folder)
        self.refresh_path_labels()
        return True

    def refresh_path_labels(self):
        self.target_game_button.setText(settings.game_name)
        self.appdata_path_label.setText(str(settings.appdata_locallow_folder))
        self.portraits_path_label.setText(str(settings.output_folder))


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print("Smoke test: All modules imported successfully.")
        sys.exit(0)

    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
