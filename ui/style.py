"""Premium Dark and Light QSS stylesheets and ThemeManager helper."""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from settings.settings_manager import SettingsManager

DARK_STYLESHEET = """
/* Global Window Styles */
QMainWindow, QDialog {
    background-color: #121214;
}

QWidget {
    color: #e4e4e7;
    font-family: "Segoe UI", "Outfit", "Inter", sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#sidebar {
    background-color: #1a1a1e;
    border-right: 1px solid #27272a;
}

QLabel#sidebarTitle {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    padding: 10px 0px;
}

QFrame#sidebarDivider {
    color: #27272a;
}

/* Navigation Buttons */
QPushButton#navBtn {
    background-color: transparent;
    color: #a1a1aa;
    text-align: left;
    padding: 10px 15px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    margin: 2px 8px;
}

QPushButton#navBtn:hover {
    background-color: #27272a;
    color: #ffffff;
}

QPushButton#navBtn:checked {
    background-color: #6366f1;
    color: #ffffff;
    font-weight: bold;
}

/* Cards & Frames */
QFrame#card {
    background-color: #1a1a1e;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 15px;
}

QLabel#cardTitle {
    color: #a1a1aa;
    font-size: 12px;
    text-transform: uppercase;
    font-weight: bold;
}

QLabel#cardValue {
    color: #ffffff;
    font-size: 24px;
    font-weight: bold;
}

/* Table Widget styling */
QTableWidget {
    background-color: #1a1a1e;
    alternate-background-color: #121214;
    border: 1px solid #27272a;
    gridline-color: #27272a;
    border-radius: 8px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #27272a;
}

QHeaderView::section {
    background-color: #202024;
    color: #a1a1aa;
    padding: 8px;
    border: none;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

QHeaderView {
    border-bottom: 1px solid #27272a;
}

/* List and Tree Views (used inside File Dialogs) */
QListView, QTreeView {
    background-color: #1a1a1e;
    border: 1px solid #27272a;
    color: #e4e4e7;
}

QListView::item:hover, QTreeView::item:hover {
    background-color: #27272a;
}

QListView::item:selected, QTreeView::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

/* Form Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background-color: #1a1a1e;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #ffffff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1px solid #6366f1;
}

QComboBox::drop-down {
    border: none;
}

/* Menus and Context Menus */
QMenu {
    background-color: #1a1a1e;
    border: 1px solid #27272a;
    color: #e4e4e7;
}

QMenu::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

/* ToolTips */
QToolTip {
    background-color: #1a1a1e;
    color: #ffffff;
    border: 1px solid #27272a;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #121214;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #121214;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #27272a;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

/* Tab Widget Custom styling */
QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background-color: #1a1a1e;
    color: #a1a1aa;
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #6366f1;
    color: #ffffff;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #27272a;
    border-radius: 4px;
    text-align: center;
    background-color: #1a1a1e;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #10b981;
    border-radius: 3px;
}

/* Regular Buttons */
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    color: #ffffff;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton#primaryBtn {
    background-color: #6366f1;
    border: none;
    color: #ffffff;
}

QPushButton#primaryBtn:hover {
    background-color: #4f46e5;
}

QPushButton#primaryBtn:pressed {
    background-color: #3730a3;
}

QPushButton#successBtn {
    background-color: #10b981;
    border: none;
    color: #ffffff;
}

QPushButton#successBtn:hover {
    background-color: #059669;
}

QPushButton#dangerBtn {
    background-color: #f43f5e;
    border: none;
    color: #ffffff;
}

QPushButton#dangerBtn:hover {
    background-color: #e11d48;
}

/* GroupBox styling */
QGroupBox {
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 20px;
    padding-top: 15px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    left: 10px;
    color: #6366f1;
}

/* Headers */
QLabel#headerTitle {
    font-size: 22px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#headerDesc {
    font-size: 13px;
    color: #a1a1aa;
}

/* Custom embedded PDF labels */
QLabel#pdfMetaLabel {
    color: #a1a1aa;
    background-color: #1a1a1e;
    border-radius: 4px;
    padding: 4px;
    font-family: monospace;
    font-size: 11px;
}
"""

LIGHT_STYLESHEET = """
/* Global Window Styles */
QMainWindow, QDialog {
    background-color: #f4f4f5;
}

QWidget {
    color: #18181b;
    font-family: "Segoe UI", "Outfit", "Inter", sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e4e4e7;
}

QLabel#sidebarTitle {
    color: #18181b;
    font-size: 18px;
    font-weight: bold;
    padding: 10px 0px;
}

QFrame#sidebarDivider {
    color: #e4e4e7;
}

/* Navigation Buttons */
QPushButton#navBtn {
    background-color: transparent;
    color: #71717a;
    text-align: left;
    padding: 10px 15px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    margin: 2px 8px;
}

QPushButton#navBtn:hover {
    background-color: #f4f4f5;
    color: #18181b;
}

QPushButton#navBtn:checked {
    background-color: #6366f1;
    color: #ffffff;
    font-weight: bold;
}

/* Cards & Frames */
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 15px;
}

QLabel#cardTitle {
    color: #71717a;
    font-size: 12px;
    text-transform: uppercase;
    font-weight: bold;
}

QLabel#cardValue {
    color: #18181b;
    font-size: 24px;
    font-weight: bold;
}

/* Table Widget styling */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    gridline-color: #e4e4e7;
    border-radius: 8px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #e4e4e7;
}

QHeaderView::section {
    background-color: #e4e4e7;
    color: #71717a;
    padding: 8px;
    border: none;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

QHeaderView {
    border-bottom: 1px solid #e4e4e7;
}

/* List and Tree Views (used inside File Dialogs) */
QListView, QTreeView {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    color: #18181b;
}

QListView::item:hover, QTreeView::item:hover {
    background-color: #f4f4f5;
}

QListView::item:selected, QTreeView::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

/* Form Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 6px;
    padding: 6px 12px;
    color: #18181b;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1px solid #6366f1;
}

QComboBox::drop-down {
    border: none;
}

/* Menus and Context Menus */
QMenu {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    color: #18181b;
}

QMenu::item:selected {
    background-color: #6366f1;
    color: #ffffff;
}

/* ToolTips */
QToolTip {
    background-color: #ffffff;
    color: #18181b;
    border: 1px solid #e4e4e7;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #f4f4f5;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #d4d4d8;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #f4f4f5;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #d4d4d8;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

/* Tab Widget Custom styling */
QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background-color: #e4e4e7;
    color: #71717a;
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #6366f1;
    color: #ffffff;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #e4e4e7;
    border-radius: 4px;
    text-align: center;
    background-color: #ffffff;
    color: #18181b;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #10b981;
    border-radius: 3px;
}

/* Regular Buttons */
QPushButton {
    background-color: #e4e4e7;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    color: #18181b;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #d4d4d8;
}

QPushButton:pressed {
    background-color: #a1a1aa;
}

QPushButton#primaryBtn {
    background-color: #6366f1;
    border: none;
    color: #ffffff;
}

QPushButton#primaryBtn:hover {
    background-color: #4f46e5;
}

QPushButton#primaryBtn:pressed {
    background-color: #3730a3;
}

QPushButton#successBtn {
    background-color: #10b981;
    border: none;
    color: #ffffff;
}

QPushButton#successBtn:hover {
    background-color: #059669;
}

QPushButton#dangerBtn {
    background-color: #f43f5e;
    border: none;
    color: #ffffff;
}

QPushButton#dangerBtn:hover {
    background-color: #e11d48;
}

/* GroupBox styling */
QGroupBox {
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    margin-top: 20px;
    padding-top: 15px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    left: 10px;
    color: #6366f1;
}

/* Headers */
QLabel#headerTitle {
    font-size: 22px;
    font-weight: bold;
    color: #18181b;
}

QLabel#headerDesc {
    font-size: 13px;
    color: #71717a;
}

/* Custom embedded PDF labels */
QLabel#pdfMetaLabel {
    color: #71717a;
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 4px;
    padding: 4px;
    font-family: monospace;
    font-size: 11px;
}
"""


class ThemeManager:
    """Centralized Theme Manager managing Dark/Light states and color resources."""
    _instance = None

    @classmethod
    def get_instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if ThemeManager._instance is not None:
            raise Exception("This class is a singleton!")
        self._current_theme = "Dark"
        self.load_theme()

    def load_theme(self):
        """Read active theme settings from DB (default to Dark)."""
        try:
            self._current_theme = SettingsManager.get("THEME", "Dark")
        except Exception:
            self._current_theme = "Dark"

    def get_current_theme(self) -> str:
        return self._current_theme

    def get_stylesheet(self) -> str:
        if self._current_theme == "Light":
            return LIGHT_STYLESHEET
        return DARK_STYLESHEET

    def apply_theme(self):
        """Apply selected theme stylesheet globally to QApplication instance."""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self.get_stylesheet())

    def set_theme(self, theme_name: str):
        """Save theme state, write to settings, and apply globally."""
        if theme_name not in ("Dark", "Light"):
            theme_name = "Dark"
        self._current_theme = theme_name
        try:
            SettingsManager.set("THEME", theme_name)
        except Exception:
            pass
        self.apply_theme()

    # Dynamic Theme-Aware Color Accessors
    def get_invalid_row_bg(self) -> QColor:
        if self._current_theme == "Light":
            return QColor("#fee2e2")  # Light pink/red warning background
        return QColor("#7f1d1d")  # Dark crimson warning background

    def get_success_color(self) -> QColor:
        if self._current_theme == "Light":
            return QColor("#15803d")  # Readable dark emerald green
        return QColor("#10b981")  # Bright green

    def get_danger_color(self) -> QColor:
        if self._current_theme == "Light":
            return QColor("#b91c1c")  # Readable dark red
        return QColor("#ef4444")  # Bright red

    def get_warning_color(self) -> QColor:
        if self._current_theme == "Light":
            return QColor("#b45309")  # Readable dark amber/yellow
        return QColor("#f59e0b")  # Bright yellow/orange
