"""Upload Payroll view for the Payroll Management System."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QProgressBar, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from workers.qthreads import ExcelParseWorker, DBSyncWorker, PdfGenerationWorker


class UploadTab(QWidget):
    """Handles Excel file selection, validation previews, and committing database synchronization."""
    
    # Custom signal emitted when database changes occur to alert other tabs
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        title_lbl = QLabel("Upload Payroll")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Select a payroll spreadsheet to parse, validate, preview, and commit.")
        desc_lbl.setObjectName("headerDesc")
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)

        # File Select Row
        file_layout = QHBoxLayout()
        self.file_lbl = QLabel("No Excel file selected.")
        self.file_lbl.setStyleSheet("color: #a1a1aa; font-style: italic;")
        file_layout.addWidget(self.file_lbl)
        
        self.select_btn = QPushButton("Select Excel")
        self.select_btn.setObjectName("primaryBtn")
        self.select_btn.clicked.connect(self.select_excel_file)
        file_layout.addWidget(self.select_btn)
        layout.addLayout(file_layout)

        # Progress Indicators
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_lbl = QLabel("")
        self.progress_lbl.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_lbl)

        # Preview Table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(8)
        self.preview_table.setHorizontalHeaderLabels([
            "Row", "Workman ID", "Name", "Phone", "Month Year", "Gross Wages", "Net Wages", "Status/Errors"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        layout.addWidget(self.preview_table)

        # Summary Statistics Layout
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(self.stats_lbl)

        # Commits Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reset_ui)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)

        self.commit_btn = QPushButton("Commit Upload")
        self.commit_btn.setObjectName("successBtn")
        self.commit_btn.setEnabled(False)
        self.commit_btn.clicked.connect(self.commit_upload_data)
        btn_layout.addWidget(self.commit_btn)
        layout.addLayout(btn_layout)

    def select_excel_file(self):
        """Open file dialog to select payroll Excel spreadsheet and start background parser."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Payroll Excel", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return

        self.file_lbl.setText(file_path)
        self.reset_preview()

        # Disable inputs during parsing
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress animation
        self.progress_lbl.setVisible(True)
        self.progress_lbl.setText("Parsing spreadsheet columns and calculations...")

        # Start parsing in background
        self.parse_worker = ExcelParseWorker(file_path)
        self.parse_worker.finished.connect(self.on_parse_finished)
        self.parse_worker.error.connect(self.on_parse_error)
        self.parse_worker.start()

    def on_parse_finished(self, result):
        """Callback when parsing is complete. Populate preview grid and metrics."""
        self.select_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        self.cancel_btn.setEnabled(True)

        self.preview_data = result
        preview_rows = result["preview_data"]
        
        self.preview_table.setRowCount(len(preview_rows))
        
        for idx, row in enumerate(preview_rows):
            # Row number
            row_num = row["row_number"] if row["row_number"] else idx + 2
            self.preview_table.setItem(idx, 0, QTableWidgetItem(str(row_num)))
            
            # Workman ID
            self.preview_table.setItem(idx, 1, QTableWidgetItem(row["workman_id"]))
            
            # Name
            self.preview_table.setItem(idx, 2, QTableWidgetItem(row["employee_name"]))
            
            # Phone
            self.preview_table.setItem(idx, 3, QTableWidgetItem(row["phone"]))
            
            # Month
            self.preview_table.setItem(idx, 4, QTableWidgetItem(row["month_year"]))
            
            # Wages
            self.preview_table.setItem(idx, 5, QTableWidgetItem(f"{float(row['gross_wages']):.2f}"))
            self.preview_table.setItem(idx, 6, QTableWidgetItem(f"{float(row['net_wages']):.2f}"))
            
            # Status Cell
            if row["is_valid"]:
                status_item = QTableWidgetItem("Valid")
                status_item.setForeground(Qt.green)
            else:
                err_msg = ", ".join(row["errors"])
                status_item = QTableWidgetItem(f"Invalid: {err_msg}")
                status_item.setForeground(Qt.red)
                
                # Highlight invalid row cells
                for col in range(8):
                    item = self.preview_table.item(idx, col)
                    if item:
                        item.setBackground(Qt.darkRed)
                        
            self.preview_table.setItem(idx, 7, status_item)

        # Update stats text
        stats_text = (
            f"Valid Rows: {result['valid_count']} | "
            f"Invalid Rows: {result['invalid_count']} | "
            f"Gross Total: {result['total_gross']:.2f} | "
            f"Net Total: {result['total_net']:.2f}"
        )
        self.stats_lbl.setText(stats_text)

        # Enable Commit only if valid rows exist
        self.commit_btn.setEnabled(result["valid_count"] > 0)

    def on_parse_error(self, err_msg):
        """Callback when parsing errors out."""
        self.select_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        QMessageBox.critical(self, "Excel Parsing Failed", f"An error occurred while parsing:\n{err_msg}")
        self.reset_ui()

    def commit_upload_data(self):
        """Commit validated data and run the background sync and PDF generation workers."""
        if not self.preview_data or not self.preview_data["raw_valid_rows"]:
            return

        confirm = QMessageBox.question(
            self, "Confirm Commit",
            f"Are you sure you want to commit {len(self.preview_data['raw_valid_rows'])} valid payroll records to the database?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return

        # Disable all buttons
        self.commit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_lbl.setVisible(True)
        self.progress_lbl.setText("Synchronizing employees and payroll tables in background...")

        # Start database synchronization in background thread
        self.sync_worker = DBSyncWorker(self.preview_data["raw_valid_rows"])
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)
        self.sync_worker.start()

    def on_sync_finished(self, record_ids_to_generate):
        """Sync finished. If records need PDF generation, trigger the PDF Generation worker."""
        if not record_ids_to_generate:
            self.on_pdf_generation_complete(0)
            return

        self.progress_lbl.setText(f"Synchronized! Generating {len(record_ids_to_generate)} PDF slips (Form VIII-C)...")
        self.progress_bar.setRange(0, len(record_ids_to_generate))
        self.progress_bar.setValue(0)

        # Start PDF Generation in background
        self.pdf_worker = PdfGenerationWorker(record_ids_to_generate)
        self.pdf_worker.progress.connect(self.on_pdf_progress)
        self.pdf_worker.finished.connect(self.on_pdf_generation_complete)
        self.pdf_worker.error.connect(self.on_sync_error)
        self.pdf_worker.start()

    def on_pdf_progress(self, current, total):
        """Update PDF generation progress bar status."""
        self.progress_bar.setValue(current)
        self.progress_lbl.setText(f"Generating PDF slips: {current} / {total} built...")

    def on_pdf_generation_complete(self, count):
        """All synchronization and PDF generation completed."""
        QMessageBox.information(
            self, "Commit Succeeded",
            f"Successfully synchronized database records and built {count} government wage slips."
        )
        self.data_changed.emit()
        self.reset_ui()

    def on_sync_error(self, err_msg):
        """Database synchronization or PDF generation failed."""
        self.select_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        QMessageBox.critical(self, "Commit Failed", f"A database transaction failed:\n{err_msg}")
        self.reset_ui()

    def reset_preview(self):
        """Clear preview widgets."""
        self.preview_table.setRowCount(0)
        self.stats_lbl.setText("")
        self.commit_btn.setEnabled(False)

    def reset_ui(self):
        """Reset the tab to starting state."""
        self.file_lbl.setText("No Excel file selected.")
        self.preview_data = None
        self.select_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.commit_btn.setEnabled(False)
        self.reset_preview()
