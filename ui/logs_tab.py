"""Logs tab for auditing WhatsApp message delivery logs and exporting them to CSV."""

import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from database.db import get_session
from database.models import PayrollRecord, Employee
from utils.logger_config import mask_pii


class LogsTab(QWidget):
    """Event log auditing dashboard showing phone-masked sending logs with CSV exporter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_items = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Row
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_lbl = QLabel("Delivery Audit Logs")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Audit sent messages history. Phone numbers, salaries, and bank accounts are automatically masked for privacy.")
        desc_lbl.setObjectName("headerDesc")
        title_layout.addWidget(title_lbl)
        title_layout.addWidget(desc_lbl)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        header_layout.addWidget(self.export_btn)
        layout.addLayout(header_layout)

        # Search and Filter row
        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Employee Name, Workman ID, Month...")
        self.search_input.textChanged.connect(self.load_logs)
        filter_layout.addWidget(self.search_input)

        filter_layout.addWidget(QLabel("Message Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Text Message", "PDF Message"])
        self.type_combo.currentTextChanged.connect(self.load_logs)
        filter_layout.addWidget(self.type_combo)

        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "Success", "Failed"])
        self.status_combo.currentTextChanged.connect(self.load_logs)
        filter_layout.addWidget(self.status_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_logs)
        filter_layout.addWidget(self.refresh_btn)
        layout.addLayout(filter_layout)

        # Logs Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Employee", "Phone", "Message Type", "Status", "Attempts", "Errors"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Enable professional copy-paste and text selection (Task 1, 2)
        from utils.copy_helpers import setup_table_copy, enable_selection_recursive
        setup_table_copy(self.table)
        enable_selection_recursive(self)

        # Initial Load
        self.load_logs()

    def load_logs(self):
        """Query payroll_records, extract WhatsApp logs, apply filters, mask PII, and populate table."""
        search_query = self.search_input.text().strip().lower()
        type_filter = self.type_combo.currentText()
        status_filter = self.status_combo.currentText()

        self.table.setRowCount(0)
        self.log_items = []

        session = get_session()
        try:
            # Fetch all records with send attempts
            records = (
                session.query(PayrollRecord)
                .filter((PayrollRecord.text_attempts > 0) | (PayrollRecord.pdf_attempts > 0))
                .order_by(PayrollRecord.updated_at.desc())
                .all()
            )

            # Generate individual log rows
            raw_log_rows = []
            for r in records:
                emp = r.employee
                phone = emp.phone if emp else ""
                
                # Text Message Send Log
                if r.text_attempts > 0:
                    raw_log_rows.append({
                        "time": r.text_last_sent or r.updated_at,
                        "name": r.employee_name,
                        "workman_id": r.workman_id,
                        "phone": phone,
                        "month_year": r.month_year,
                        "type": "Text Message",
                        "status": r.text_status,
                        "attempts": r.text_attempts,
                        "error": r.text_error or ""
                    })

                # PDF Message Send Log
                if r.pdf_attempts > 0:
                    raw_log_rows.append({
                        "time": r.pdf_last_sent or r.updated_at,
                        "name": r.employee_name,
                        "workman_id": r.workman_id,
                        "phone": phone,
                        "month_year": r.month_year,
                        "type": "PDF Message",
                        "status": r.pdf_status,
                        "attempts": r.pdf_attempts,
                        "error": r.pdf_error or ""
                    })

            # Sort logs chronologically descending
            raw_log_rows.sort(key=lambda x: x["time"] if x["time"] else datetime.min, reverse=True)

            # Filter logs
            for log in raw_log_rows:
                # Type Filter
                if type_filter != "All" and log["type"] != type_filter:
                    continue
                # Status Filter
                if status_filter != "All" and log["status"] != status_filter:
                    continue
                # Search query
                if search_query:
                    matches = (
                        search_query in log["name"].lower() or
                        search_query in log["workman_id"].lower() or
                        search_query in log["month_year"].lower()
                    )
                    if not matches:
                        continue
                self.log_items.append(log)

            # Populate table
            self.table.setRowCount(len(self.log_items))
            for idx, log in enumerate(self.log_items):
                time_str = log["time"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(log["time"], datetime) else str(log["time"])
                self.table.setItem(idx, 0, QTableWidgetItem(time_str))
                self.table.setItem(idx, 1, QTableWidgetItem(f"{log['name']} ({log['workman_id']})"))
                
                # Mask phone and errors
                masked_phone = mask_pii(log["phone"])
                self.table.setItem(idx, 2, QTableWidgetItem(masked_phone))
                
                self.table.setItem(idx, 3, QTableWidgetItem(log["type"]))
                
                # Status
                status_item = QTableWidgetItem(log["status"])
                if log["status"] == "Success":
                    status_item.setForeground(Qt.green)
                elif log["status"] == "Failed":
                    status_item.setForeground(Qt.red)
                self.table.setItem(idx, 4, status_item)
                
                self.table.setItem(idx, 5, QTableWidgetItem(str(log["attempts"])))
                
                masked_err = mask_pii(log["error"])
                self.table.setItem(idx, 6, QTableWidgetItem(masked_err))

        except Exception as e:
            QMessageBox.critical(self, "Load Failed", f"Could not load log history:\n{str(e)}")
        finally:
            session.close()

    def export_to_csv(self):
        """Open a file save dialog and export currently filtered list to CSV."""
        if not self.log_items:
            QMessageBox.warning(self, "No Logs", "No log entries available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Logs CSV", "payroll_delivery_logs.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Write headers
                writer.writerow(["Timestamp", "Employee Name", "Workman ID", "Phone", "Message Type", "Status", "Attempts", "Error Details"])
                for log in self.log_items:
                    time_str = log["time"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(log["time"], datetime) else str(log["time"])
                    writer.writerow([
                        time_str,
                        log["name"],
                        log["workman_id"],
                        mask_pii(log["phone"]),
                        log["type"],
                        log["status"],
                        log["attempts"],
                        mask_pii(log["error"])
                    ])
            QMessageBox.information(self, "Export Succeeded", f"Delivery logs successfully exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred while writing CSV:\n{str(e)}")
