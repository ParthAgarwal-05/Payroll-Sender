"""Dashboard view for the Payroll Management System."""

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QComboBox, QPushButton, QGridLayout, QHeaderView
)
from PySide6.QtCore import Qt
from services.payroll_service import PayrollService


class DashboardTab(QWidget):
    """Tab showing key payroll status cards and recent log activities."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header Row
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_label = QLabel("Dashboard")
        title_label.setObjectName("headerTitle")
        desc_label = QLabel("Overview of monthly payroll operations and delivery status.")
        desc_label.setObjectName("headerDesc")
        title_layout.addWidget(title_label)
        title_layout.addWidget(desc_label)
        header_layout.addLayout(title_layout)

        header_layout.addStretch()

        # Month Selector dropdown
        header_layout.addWidget(QLabel("Payroll Month:"))
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(150)
        self.month_combo.currentTextChanged.connect(self.on_month_changed)
        header_layout.addWidget(self.month_combo)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("primaryBtn")
        self.refresh_btn.clicked.connect(self.refresh_dashboard)
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        # Grid for stats cards
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(15)
        layout.addLayout(self.cards_layout)

        # Stats Cards definitions (Row, Col, Label, Key)
        self.card_definitions = [
            (0, 0, "Current Payroll Month", "month_year"),
            (0, 1, "Employees Profiled", "total_employees"),
            (0, 2, "Payroll Records", "total_records"),
            (1, 0, "PDFs Generated", "pdfs_generated"),
            (1, 1, "PDFs Pending", "pdfs_pending"),
            (1, 2, "Retry Queue", "retry_queue"),
            (2, 0, "Text Messages Sent", "texts_sent"),
            (2, 1, "PDF Messages Sent", "pdfs_sent"),
            (2, 2, "Failed Messages", "failed_messages"),
        ]

        self.cards = {}
        for r, c, label, key in self.card_definitions:
            card_frame = QWidget()
            card_frame.setObjectName("card")
            card_layout = QVBoxLayout(card_frame)
            card_layout.setContentsMargins(15, 15, 15, 15)
            
            title_lbl = QLabel(label)
            title_lbl.setObjectName("cardTitle")
            val_lbl = QLabel("0")
            val_lbl.setObjectName("cardValue")
            
            card_layout.addWidget(title_lbl)
            card_layout.addWidget(val_lbl)
            self.cards[key] = val_lbl
            self.cards_layout.addWidget(card_frame, r, c)

        # Recent Activity section
        activity_title = QLabel("Recent Payroll Activity")
        activity_title.setObjectName("headerTitle")
        layout.addWidget(activity_title)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(6)
        self.activity_table.setHorizontalHeaderLabels([
            "Timestamp", "Employee Name", "Workman ID", "Operation", "Status", "Details"
        ])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.activity_table.setAlternatingRowColors(True)
        layout.addWidget(self.activity_table)

        # Enable professional copy-paste and text selection (Task 1, 2)
        from utils.copy_helpers import setup_table_copy, enable_selection_recursive
        setup_table_copy(self.activity_table)
        enable_selection_recursive(self)

    def refresh_months_list(self):
        """Reload the distinct months from the database."""
        current = self.month_combo.currentText()
        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        
        months = PayrollService.get_distinct_months()
        self.month_combo.addItems(months)
        
        if current in months:
            self.month_combo.setCurrentText(current)
        elif months:
            self.month_combo.setCurrentIndex(0)
            
        self.month_combo.blockSignals(False)

    def on_month_changed(self, month):
        """Instantly refresh stats and activity logs when active month dropdown value changes."""
        self.refresh_dashboard()

    def refresh_dashboard(self):
        """Update dashboard statistics cards and recent activity tables from the database."""
        # Refresh months combobox without resetting current selection
        self.refresh_months_list()
        
        selected_month = self.month_combo.currentText()
        if not selected_month:
            # Set defaults if empty
            for key, widget in self.cards.items():
                widget.setText("—")
            self.activity_table.setRowCount(0)
            return

        # Load Stats
        stats = PayrollService.get_dashboard_stats(selected_month)
        for key, widget in self.cards.items():
            if key == "month_year":
                widget.setText(selected_month)
            else:
                widget.setText(str(stats.get(key, 0)))

        # Load Recent Activity
        activities = PayrollService.get_recent_activity(selected_month, limit=20)
        self.activity_table.setRowCount(len(activities))
        
        for idx, act in enumerate(activities):
            time_str = act["time"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(act["time"], datetime) else str(act["time"])
            self.activity_table.setItem(idx, 0, QTableWidgetItem(time_str))
            self.activity_table.setItem(idx, 1, QTableWidgetItem(act["name"]))
            self.activity_table.setItem(idx, 2, QTableWidgetItem(act["workman_id"] or ""))
            self.activity_table.setItem(idx, 3, QTableWidgetItem(act["operation"]))
            
            # Status Cell
            status_item = QTableWidgetItem(act["status"])
            if act["status"] == "Success":
                status_item.setForeground(Qt.green)
            elif act["status"] == "Failed":
                status_item.setForeground(Qt.red)
            self.activity_table.setItem(idx, 4, QTableWidgetItem(status_item))
            
            details = act["error"] if act["error"] else (f"Attempts: {act['attempts']}" if act["attempts"] > 1 else "OK")
            self.activity_table.setItem(idx, 5, QTableWidgetItem(details))
