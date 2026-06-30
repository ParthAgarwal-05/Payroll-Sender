"""Main application window container for the Payroll & WhatsApp Management System."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon


from ui.dashboard_tab import DashboardTab
from ui.upload_tab import UploadTab
from ui.wageslips_tab import WageSlipsTab
from ui.send_text_tab import SendTextTab
from ui.send_pdf_tab import SendPdfTab
from ui.settings_tab import SettingsTab
from ui.logs_tab import LogsTab


class MainWindow(QMainWindow):
    """Main application frame with navigation sidebar and stacked views."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Payroll Manager - Desktop & WhatsApp Management System")
        self.resize(1280, 800)
        

        
        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout: Horizontal (Sidebar + Stacked Content)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------- SIDEBAR -----------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        sidebar_layout.setSpacing(5)

        # Brand / App Title
        brand_lbl = QLabel("PAYROLL MANAGER")
        brand_lbl.setObjectName("sidebarTitle")
        brand_lbl.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(brand_lbl)
        
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("margin-bottom: 10px;")
        sidebar_layout.addWidget(divider)

        # Navigation buttons mapping (Tab Name, Button Icon text or Emoji)
        self.nav_items = [
            ("Dashboard", "🏠 Dashboard"),
            ("Upload Payroll", "📥 Upload Payroll"),
            ("Wage Slips", "📄 Wage Slips"),
            ("Send Text", "💬 Send Text"),
            ("Send PDF", "📎 Send PDF"),
            ("Settings", "⚙️ Settings"),
            ("Logs", "📜 Logs"),
        ]

        self.nav_buttons = []
        for index, (key, label) in enumerate(self.nav_items):
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.clicked.connect(lambda checked, idx=index: self.on_nav_clicked(idx))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Version stamp
        version_lbl = QLabel("v1.0.0")
        version_lbl.setStyleSheet("color: #71717a; font-size: 11px; padding-left: 20px;")
        sidebar_layout.addWidget(version_lbl)

        main_layout.addWidget(sidebar)

        # ----------------- MAIN STACKED CONTENT -----------------
        self.stacked_widget = QStackedWidget()
        
        # Instantiate tabs
        self.dashboard_tab = DashboardTab()
        self.upload_tab = UploadTab()
        self.wageslips_tab = WageSlipsTab()
        self.send_text_tab = SendTextTab()
        self.send_pdf_tab = SendPdfTab()
        self.settings_tab = SettingsTab()
        self.logs_tab = LogsTab()

        # Add tabs in chronological index matching nav_items
        self.stacked_widget.addWidget(self.dashboard_tab)
        self.stacked_widget.addWidget(self.upload_tab)
        self.stacked_widget.addWidget(self.wageslips_tab)
        self.stacked_widget.addWidget(self.send_text_tab)
        self.stacked_widget.addWidget(self.send_pdf_tab)
        self.stacked_widget.addWidget(self.settings_tab)
        self.stacked_widget.addWidget(self.logs_tab)

        main_layout.addWidget(self.stacked_widget)

        # Select first tab by default
        self.on_nav_clicked(0)

        # Enable text selection on all QLabels globally inside main window container (Task 1)
        from utils.copy_helpers import enable_selection_recursive
        enable_selection_recursive(self)

    def setup_signals(self):
        """Bind custom signals to keep different tabs synchronized when database commits occur."""
        # When upload commits data, refresh other views
        self.upload_tab.data_changed.connect(self.refresh_all_tabs)
        
        # When wage slips list deletes or regenerates a PDF, refresh dashboard/logs/sending lists
        self.wageslips_tab.data_changed.connect(self.refresh_all_tabs)
        
        # When sends occur, refresh logs and dashboard
        self.send_text_tab.data_changed.connect(self.refresh_all_tabs)
        self.send_pdf_tab.data_changed.connect(self.refresh_all_tabs)

    def on_nav_clicked(self, active_index):
        """Handle sidebar button click, transition stack, and sync checklist statuses."""
        self.stacked_widget.setCurrentIndex(active_index)
        
        # Update checked statuses on sidebar button group
        for idx, btn in enumerate(self.nav_buttons):
            btn.setChecked(idx == active_index)

        # Trigger automatic refreshes of target tab data when viewing
        widget = self.stacked_widget.widget(active_index)
        if hasattr(widget, "refresh_dashboard"):
            widget.refresh_dashboard()
        elif hasattr(widget, "refresh_data"):
            widget.refresh_data()
        elif hasattr(widget, "load_logs"):
            widget.load_logs()

    def refresh_all_tabs(self):
        """Cross-tab refresh callback trigger."""
        self.dashboard_tab.refresh_dashboard()
        self.wageslips_tab.refresh_data()
        self.send_text_tab.refresh_data()
        self.send_pdf_tab.refresh_data()
        self.logs_tab.load_logs()

    def closeEvent(self, event):
        """Clean up active background worker threads when closing window."""
        for tab in (self.upload_tab, self.wageslips_tab, self.send_text_tab, self.send_pdf_tab, self.settings_tab):
            if hasattr(tab, "cleanup_workers"):
                try:
                    tab.cleanup_workers()
                except Exception:
                    pass
        event.accept()
