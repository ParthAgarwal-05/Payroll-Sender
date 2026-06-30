"""Wage Slips page for viewing payroll runs, generating PDFs, and managing records."""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QProgressBar, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from database.db import get_session
from database.models import PayrollRecord, Employee
from services.payroll_service import PayrollService
from services.pdf_service import PdfService
from ui.pdf_preview import PdfPreviewDialog, open_file_in_default_viewer
from workers.qthreads import PdfGenerationWorker


class WageSlipsTab(QWidget):
    """Tab showing Excel-like list of monthly payroll records and management controls."""
    
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Row
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_lbl = QLabel("Wage Slips (Form VIII-C)")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Manage government-style wage slips, preview PDFs, and audit sending logs.")
        desc_lbl.setObjectName("headerDesc")
        title_layout.addWidget(title_lbl)
        title_layout.addWidget(desc_lbl)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Month filter dropdown
        header_layout.addWidget(QLabel("Select Month:"))
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(150)
        self.month_combo.currentTextChanged.connect(self.load_records)
        header_layout.addWidget(self.month_combo)
        layout.addLayout(header_layout)

        # Filter & Search Row
        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Employee, Phone, Workman ID, Month, UAN...")
        self.search_input.textChanged.connect(self.load_records)
        filter_layout.addWidget(self.search_input)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_btn)
        layout.addLayout(filter_layout)

        # Progress indicator for regeneration
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Main Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Workman ID", "Employee Name", "Phone", "Month", "Gross", "Net",
            "PDF Status", "Text Status", "PDF Msg Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        # Set specific column widths to ensure horizontal scrolling instead of shrinking buttons
        self.table.setColumnWidth(0, 100) # Workman ID
        self.table.setColumnWidth(1, 150) # Employee Name
        self.table.setColumnWidth(2, 110) # Phone
        self.table.setColumnWidth(3, 100) # Month
        self.table.setColumnWidth(4, 90)  # Gross
        self.table.setColumnWidth(5, 90)  # Net
        self.table.setColumnWidth(6, 100) # PDF Status
        self.table.setColumnWidth(7, 100) # Text Status
        self.table.setColumnWidth(8, 110) # PDF Msg Status
        self.table.setColumnWidth(9, 640) # Actions (all 4 buttons fit cleanly)
        
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.verticalHeader().setDefaultSectionSize(52)
        layout.addWidget(self.table)

        # Enable professional copy-paste and text selection (Task 1, 2)
        from utils.copy_helpers import setup_table_copy, enable_selection_recursive
        setup_table_copy(self.table)
        enable_selection_recursive(self)

    def refresh_months(self):
        """Update distinct month list in the dropdown filter."""
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

    def refresh_data(self):
        """Reload months dropdown and then trigger records query."""
        self.refresh_months()
        self.load_records()

    def load_records(self):
        """Query SQLite database for payroll records matching selected filters."""
        selected_month = self.month_combo.currentText()
        search_query = self.search_input.text().strip().lower()
        
        self.table.setRowCount(0)
        
        if not selected_month:
            return

        session = get_session()
        try:
            # Query payroll records for selected month
            query = session.query(PayrollRecord).filter_by(month_year=selected_month)
            
            # Retrieve all matching rows
            records = query.all()
            
            # Filter rows locally in Python for flexible multi-column matching
            filtered_records = []
            for r in records:
                emp = r.employee
                emp_phone = emp.phone if emp else ""
                emp_uan = r.uan if r.uan else ""
                
                # Check search matches
                if search_query:
                    matches = (
                        search_query in r.workman_id.lower() or
                        search_query in r.employee_name.lower() or
                        search_query in emp_phone.lower() or
                        search_query in r.month_year.lower() or
                        search_query in emp_uan.lower()
                    )
                    if not matches:
                        continue
                filtered_records.append(r)

            self.table.setRowCount(len(filtered_records))
            
            for idx, r in enumerate(filtered_records):
                emp = r.employee
                
                # Setup items
                self.table.setItem(idx, 0, QTableWidgetItem(r.workman_id))
                self.table.setItem(idx, 1, QTableWidgetItem(r.employee_name))
                self.table.setItem(idx, 2, QTableWidgetItem(emp.phone if emp else "—"))
                self.table.setItem(idx, 3, QTableWidgetItem(r.month_year))
                self.table.setItem(idx, 4, QTableWidgetItem(f"{float(r.gross_wages):.2f}"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{float(r.net_wages):.2f}"))
                
                # PDF Status Item
                pdf_status = "Generated" if r.pdf_generated else "Pending"
                pdf_item = QTableWidgetItem(pdf_status)
                if r.pdf_generated:
                    pdf_item.setForeground(Qt.green)
                else:
                    pdf_item.setForeground(Qt.yellow)
                self.table.setItem(idx, 6, pdf_item)

                # Text Status Item
                text_item = QTableWidgetItem(r.text_status)
                if r.text_status == "Success":
                    text_item.setForeground(Qt.green)
                elif r.text_status == "Failed":
                    text_item.setForeground(Qt.red)
                self.table.setItem(idx, 7, text_item)

                # PDF Message Status Item
                pdf_msg_item = QTableWidgetItem(r.pdf_status)
                if r.pdf_status == "Success":
                    pdf_msg_item.setForeground(Qt.green)
                elif r.pdf_status == "Failed":
                    pdf_msg_item.setForeground(Qt.red)
                self.table.setItem(idx, 8, pdf_msg_item)

                # Create Cell Widget for Row Actions
                actions_widget = QWidget()
                actions_widget.setMinimumHeight(46)
                actions_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(8, 4, 8, 4)
                actions_layout.setSpacing(12)
                actions_layout.setAlignment(Qt.AlignCenter)

                # Action buttons using the helper function
                preview_btn = create_action_button(
                    text="Preview PDF",
                    standard_pixmap=QStyle.SP_FileDialogContentsView,
                    theme_name="document-properties",
                    color_hex="#2563eb",
                    hover_color_hex="#3b82f6",
                    tooltip="Preview PDF Slip",
                    callback=lambda checked=False, rid=r.id: self.preview_pdf_record(rid),
                    min_width=145
                )
                actions_layout.addWidget(preview_btn)

                folder_btn = create_action_button(
                    text="Open Folder",
                    standard_pixmap=QStyle.SP_DirOpenIcon,
                    theme_name="folder-open",
                    color_hex="#d97706",
                    hover_color_hex="#f59e0b",
                    tooltip="Open containing folder",
                    callback=lambda checked=False, rid=r.id: self.open_pdf_folder(rid),
                    min_width=145
                )
                actions_layout.addWidget(folder_btn)

                regen_btn = create_action_button(
                    text="Regenerate",
                    standard_pixmap=QStyle.SP_BrowserReload,
                    theme_name="view-refresh",
                    color_hex="#16a34a",
                    hover_color_hex="#22c55e",
                    tooltip="Regenerate PDF Slip",
                    callback=lambda checked=False, rid=r.id: self.regenerate_pdf(rid),
                    min_width=145
                )
                actions_layout.addWidget(regen_btn)

                delete_btn = create_action_button(
                    text="Delete",
                    standard_pixmap=QStyle.SP_TrashIcon,
                    theme_name="edit-delete",
                    color_hex="#dc2626",
                    hover_color_hex="#ef4444",
                    tooltip="Delete Payroll Record",
                    callback=lambda checked=False, rid=r.id: self.delete_record(rid),
                    min_width=120
                )
                actions_layout.addWidget(delete_btn)

                self.table.setCellWidget(idx, 9, actions_widget)
                self.table.setRowHeight(idx, 52)
                
        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Failed to retrieve payroll history:\n{str(e)}")
        finally:
            session.close()

    def preview_pdf_record(self, record_id: int):
        """Load record, ensure PDF is generated, and open preview dialog."""
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=record_id).first()
            if not record:
                QMessageBox.warning(self, "Record Not Found", f"Payroll record ID {record_id} does not exist.")
                return

            pdf_path = record.pdf_path
            emp_name = record.employee_name

            # If PDF is not generated yet, generate it now
            if not pdf_path or not r_exists(pdf_path):
                try:
                    pdf_path = PdfService.generate_and_save(record_id)
                    # Refresh record from DB to get the new path
                    record = session.query(PayrollRecord).filter_by(id=record_id).first()
                    pdf_path = record.pdf_path
                    self.load_records()
                except Exception as e:
                    QMessageBox.critical(self, "PDF Build Failed", f"Could not build PDF slip:\n{str(e)}")
                    return

            file_exists = r_exists(pdf_path)

            # Debug logging (Task 4)
            print("\nPreview PDF")
            print(f"Record ID: {record_id}")
            print(f"Employee: {emp_name}")
            print(f"Path: {pdf_path}")
            print(f"Exists: {file_exists}\n")

            if not file_exists:
                QMessageBox.critical(self, "File Not Found", f"The PDF file does not exist at:\n{pdf_path}")
                return

            # Open Dialog
            dialog = PdfPreviewDialog(pdf_path, self)
            dialog.exec()
        except Exception as ex:
            QMessageBox.critical(self, "Preview Error", f"An error occurred while launching preview:\n{str(ex)}")
        finally:
            session.close()

    def open_pdf_folder(self, record_id: int):
        """Open the parent directory of the generated PDF in the file browser."""
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=record_id).first()
            if not record or not record.pdf_path:
                QMessageBox.critical(self, "File Missing", "PDF slip has not been generated for this record yet.")
                return
                
            pdf_path = record.pdf_path
            
            if r_exists(pdf_path):
                parent_dir = str(Path(pdf_path).parent)
                open_file_in_default_viewer(parent_dir)
            else:
                QMessageBox.warning(self, "File Not Found", f"PDF file was not found at:\n{pdf_path}")
        except Exception as e:
            QMessageBox.critical(self, "Folder Opening Failed", f"Could not open directory:\n{str(e)}")
        finally:
            session.close()

    def regenerate_pdf(self, record_id: int):
        """Trigger PDF generation in a background thread."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # animate loading

        self.pdf_worker = PdfGenerationWorker([record_id])
        self.pdf_worker.finished.connect(self.on_regen_finished)
        self.pdf_worker.error.connect(self.on_regen_error)
        self.pdf_worker.start()

    def on_regen_finished(self):
        """PDF regeneration completed successfully."""
        self.progress_bar.setVisible(False)
        self.load_records()
        self.data_changed.emit()

    def on_regen_error(self, err_msg):
        """PDF regeneration failed."""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Regeneration Failed", f"PDF rebuild failed:\n{err_msg}")

    def delete_record(self, record_id: int):
        """Deletes only that month's payroll record, preserving the employee profile."""
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this payroll record?\n"
            "This will delete the monthly run and its generated PDF, but the employee profile will remain intact.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return

        try:
            PayrollService.delete_payroll_record(record_id)
            QMessageBox.information(self, "Deleted", "Payroll record deleted successfully.")
            self.load_records()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"An error occurred while deleting:\n{str(e)}")


def r_exists(path: str | None) -> bool:
    """Safe check if file exists using pathlib."""
    if not path:
        return False
    try:
        return Path(path).exists()
    except Exception:
        return False


def create_action_button(
    text: str,
    standard_pixmap: QStyle.StandardPixmap,
    theme_name: str,
    color_hex: str,
    hover_color_hex: str,
    tooltip: str,
    callback,
    min_width: int
) -> QPushButton:
    """Reusable helper function to create styled action buttons with text, icon, and colors."""
    btn = QPushButton()
    
    # Try to load platform-native icon theme first, fallback to QStyle standard pixmaps
    icon = QIcon.fromTheme(theme_name)
    if icon.isNull():
        style = QApplication.style()
        if style:
            icon = style.standardIcon(standard_pixmap)
            
    btn.setIcon(icon)
    btn.setIconSize(QSize(22, 22)) # Larger icons for desktop look (Task 4)
    btn.setText(text)
    
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    
    # Set bold font and larger size (Task 7)
    font = btn.font()
    font.setPointSize(10)
    font.setBold(True)
    btn.setFont(font)
    
    # Fixed button dimensions (Task 3)
    btn.setFixedHeight(38)
    btn.setFixedWidth(min_width)
    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    
    # Connect callback safely (Task 9)
    if callback:
        btn.clicked.connect(callback)
        
    # Stylesheet layout properties (Task 4, 8)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {color_hex};
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding-left: 14px;
            padding-right: 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {hover_color_hex};
            border: 1px solid rgba(255, 255, 255, 0.25);
        }}
        QPushButton:pressed {{
            background-color: {color_hex};
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
    """)
    return btn
