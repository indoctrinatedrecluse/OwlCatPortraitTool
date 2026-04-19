from io import BytesIO
import random
import string
from pathlib import Path

import requests
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

from GlobalsService import (
    get_available_games,
    get_full_length_portrait_size,
    get_required_portrait_dimensions,
    set_appdata_locallow_folder,
    set_game_name,
    settings,
)
from SearchService import search_portraits_by_tags
from URLService import get_image_from_url, is_valid_url


PORTRAIT_EDITOR_TAB_INDEX = 0
IMAGE_REQUEST_TIMEOUT_SECONDS = 20
MIN_THUMBNAIL_WIDTH = 150
MAX_THUMBNAIL_WIDTH = 220
RESULT_CELL_PADDING = 24
RESULT_CELL_SPACING = 12
IMAGE_REQUEST_HEADERS = {
    "User-Agent": "OwlcatPortraitTool/1.0",
}
LOCAL_OUTPUT_FOLDER = Path(__file__).resolve().parent / "output"
PORTRAIT_FOLDER_NAME_LENGTH = 16
PORTRAIT_FOLDER_ALPHABET = string.ascii_uppercase + string.digits


class MainWindow(QtWidgets.QMainWindow):
    """Main application window with one tab per screen."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Owlcat Portrait Tool")
        self.setGeometry(100, 100, 800, 600)

        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.setup_portrait_editor_tab()
        self.setup_search_tab()
        self.setup_settings_tab()

    def setup_portrait_editor_tab(self):
        self.portrait_editor_tab = PortraitEditorTab()
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


class PortraitEditorTab(QtWidgets.QWidget):
    """Screen 1: portrait loading and editing."""

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.source_url = None
        self.source_image = None

        self.source_label = QtWidgets.QLabel("No portrait selected")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.source_label)

        self.crop_canvas = PortraitCropCanvas()
        layout.addWidget(self.crop_canvas, stretch=1)

        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(button_layout)

        self.export_local_button = QtWidgets.QPushButton("Export Local")
        self.export_local_button.clicked.connect(self.export_local)
        self.export_local_button.setEnabled(False)
        button_layout.addWidget(self.export_local_button)

        self.export_game_button = QtWidgets.QPushButton("Export To Game")
        self.export_game_button.clicked.connect(self.export_to_game)
        self.export_game_button.setEnabled(False)
        button_layout.addWidget(self.export_game_button)

        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_source_url(self, image_url):
        self.source_url = image_url
        self.source_label.setText(f"Selected portrait source:\n{image_url}")
        self.status_label.setText("Loading image...")
        self.export_local_button.setEnabled(False)
        self.export_game_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            self.source_image = get_image_from_url(image_url).convert("RGBA")
        except Exception as error:
            self.source_image = None
            self.crop_canvas.clear_image()
            self.status_label.setText(f"Could not load image: {error}")
            return

        self.crop_canvas.set_image(self.source_image)
        self.export_local_button.setEnabled(True)
        self.export_game_button.setEnabled(True)
        self.status_label.setText("Drag the image to position it inside the crop outline.")

    def export_local(self):
        self.export_portrait_set(LOCAL_OUTPUT_FOLDER)

    def export_to_game(self):
        self.export_portrait_set(settings.output_folder)

    def export_portrait_set(self, output_root):
        if self.source_image is None:
            self.status_label.setText("Load an image before exporting.")
            return

        output_folder = create_unique_portrait_folder(output_root)

        cropped_image = self.crop_canvas.get_cropped_image()
        for portrait_size in get_required_portrait_dimensions():
            output_image = cropped_image.resize(
                (portrait_size.width, portrait_size.height),
                Image.Resampling.LANCZOS,
            )
            output_image.save(output_folder / portrait_size.name)

        self.status_label.setText(f"Exported portrait set to:\n{output_folder}")


class PortraitCropCanvas(QtWidgets.QWidget):
    """Draggable image preview with a fixed Pathfinder full-length crop frame."""

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
            self.drag_start_pos = None
            self.drag_start_offset = None
            self.setCursor(QtCore.Qt.ArrowCursor)

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

        self.input_switch = QtWidgets.QCheckBox("URL Input")
        self.input_switch.setChecked(True)
        layout.addWidget(self.input_switch)

        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Enter URL or tags...")
        layout.addWidget(self.search_bar)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.process_search)
        layout.addWidget(self.search_button)

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

    def get_search_input(self):
        text = self.search_bar.text().strip()
        if self.input_switch.isChecked():
            return text

        return [tag.strip() for tag in text.split(",") if tag.strip()]

    def process_search(self):
        self.render_search_results()

    def render_search_results(self):
        """Render URL or tag-search results into the scrollable results list."""
        self.image_result_widgets = []
        self.results_list.clear()
        search_input = self.get_search_input()

        if not search_input:
            self.results_list.addItem("Enter a URL or at least one tag.")
            return

        if self.input_switch.isChecked():
            self.handle_url_input(search_input)
            return

        self.render_tag_search_results(search_input)

    def handle_url_input(self, url):
        if not is_valid_url(url):
            self.results_list.addItem("Enter a valid HTTP or HTTPS image URL.")
            return

        self.main_window.open_portrait_editor_with_url(url)

    def open_selected_result(self, item):
        image_url = item.data(QtCore.Qt.UserRole)
        if image_url:
            self.main_window.open_portrait_editor_with_url(image_url)

    def render_tag_search_results(self, tags):
        self.results_list.addItem("Searching...")
        QtWidgets.QApplication.processEvents()

        try:
            results = search_portraits_by_tags(tags)
        except Exception as error:
            self.results_list.clear()
            self.results_list.addItem(f"Search failed: {error}")
            return

        self.results_list.clear()
        if not results:
            self.results_list.addItem("No results found.")
            return

        self.image_result_widgets = []
        self.update_results_grid_size()

        for result in results:
            QtWidgets.QApplication.processEvents()

            try:
                pixmap = self.load_image_preview(result)
            except Exception as error:
                self.results_list.addItem(
                    f"Could not load image: {result.image_url} ({error})"
                )
                continue

            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(self.results_list.gridSize())
            item.setData(QtCore.Qt.UserRole, result.image_url)
            self.results_list.addItem(item)

            image_label = QtWidgets.QLabel()
            image_label.setAlignment(QtCore.Qt.AlignCenter)
            image_label.setCursor(QtCore.Qt.PointingHandCursor)
            image_label.setToolTip(self.format_result_tooltip(result))
            self.results_list.setItemWidget(item, image_label)
            self.image_result_widgets.append((item, image_label, pixmap))

        self.update_result_images()

    def load_image_preview(self, result):
        preview_url = result.preview_url or result.image_url
        response = requests.get(
            preview_url,
            headers=IMAGE_REQUEST_HEADERS,
            timeout=IMAGE_REQUEST_TIMEOUT_SECONDS,
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

        return QtGui.QPixmap.fromImage(qt_image)

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
        icon_size = self.results_list.iconSize()

        for _, image_label, pixmap in self.image_result_widgets:
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


class SettingsTab(QtWidgets.QWidget):
    """Screen 3: application settings."""

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)

        self.game_selector = QtWidgets.QComboBox()
        self.game_selector.addItems(get_available_games())
        self.game_selector.setCurrentText(settings.game_name)
        self.game_selector.currentTextChanged.connect(self.change_game)
        layout.addRow("Game", self.game_selector)

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

    def change_game(self, game_name):
        set_game_name(game_name)
        self.refresh_path_labels()

    def choose_appdata_path(self):
        selected_folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Game AppData Folder",
            str(settings.appdata_locallow_folder),
        )

        if not selected_folder:
            return

        set_appdata_locallow_folder(selected_folder)
        self.refresh_path_labels()

    def refresh_path_labels(self):
        self.appdata_path_label.setText(str(settings.appdata_locallow_folder))
        self.portraits_path_label.setText(str(settings.output_folder))


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
