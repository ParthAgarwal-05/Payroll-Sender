"""Premium Dark QSS stylesheet and theme helper."""

DARK_STYLESHEET = """
/* Global Window Styles */
QMainWindow {
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
}

QPushButton#successBtn:hover {
    background-color: #059669;
}

QPushButton#dangerBtn {
    background-color: #f43f5e;
    border: none;
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
"""
