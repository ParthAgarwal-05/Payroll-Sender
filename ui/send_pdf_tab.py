"""Send PDF Messages tab for distributing payslips as PDF document messages via WhatsApp Cloud API."""

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QProgressBar, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from database.db import get_session
from database.models import PayrollRecord, Employee
from services.payroll_service import PayrollService
from workers.qthreads import WhatsAppSendWorker


class SendPdfTab(QWidget):
    """View to select and send PDF document slips using Meta Cloud API and Media API."""
    
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Row
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_lbl = QLabel("Send PDF Messages")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Distribute PDF wage slips using Meta Media API uploads and document deliveries.")
        desc_lbl.setObjectName("headerDesc")
        title_layout.addWidget(title_lbl)
        title_layout.addWidget(desc_lbl)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Month Selector
        header_layout.addWidget(QLabel("Payroll Month:"))
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(150)
        self.month_combo.currentTextChanged.connect(self.load_records)
        header_layout.addWidget(self.month_combo)
        layout.addLayout(header_layout)

        # Filters Row
        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Employee Name, Phone, Workman ID...")
        self.search_input.textChanged.connect(self.load_records)
        filter_layout.addWidget(self.search_input)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_btn)
        layout.addLayout(filter_layout)

        # Multi-Select Actions Row
        action_layout = QHBoxLayout()
        
        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.stateChanged.connect(self.toggle_select_all)
        action_layout.addWidget(self.select_all_cb)

        self.send_selected_btn = QPushButton("Send Selected")
        self.send_selected_btn.setObjectName("primaryBtn")
        self.send_selected_btn.clicked.connect(self.send_selected)
        action_layout.addWidget(self.send_selected_btn)

        self.send_pending_btn = QPushButton("Send All Pending")
        self.send_pending_btn.clicked.connect(self.send_all_pending)
        action_layout.addWidget(self.send_pending_btn)

        self.retry_failed_btn = QPushButton("Retry Failed")
        self.retry_failed_btn.setObjectName("dangerBtn")
        self.retry_failed_btn.clicked.connect(self.retry_failed_records)
        action_layout.addWidget(self.retry_failed_btn)
        
        action_layout.addStretch()
        
        self.abort_btn = QPushButton("Abort")
        self.abort_btn.setObjectName("dangerBtn")
        self.abort_btn.setVisible(False)
        self.abort_btn.clicked.connect(self.abort_sending)
        action_layout.addWidget(self.abort_btn)
        
        layout.addLayout(action_layout)

        # Progress widgets
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_lbl = QLabel("")
        self.progress_lbl.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_lbl)

        # Table Grid
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "Workman ID", "Employee Name", "Phone", "Gross Wages", "Net Wages",
            "PDF Msg Status", "Attempts", "Last Sent"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
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
        """Query SQLite database for payroll records and update UI grid status."""
        if self.worker and self.worker.isRunning():
            return

        selected_month = self.month_combo.currentText()
        search_query = self.search_input.text().strip().lower()
        
        self.table.setRowCount(0)
        self.select_all_cb.setChecked(False)
        
        if not selected_month:
            return

        session = get_session()
        try:
            records = session.query(PayrollRecord).filter_by(month_year=selected_month).all()
            
            # Filter rows locally
            filtered_records = []
            for r in records:
                emp = r.employee
                emp_phone = emp.phone if emp else ""
                
                if search_query:
                    matches = (
                        search_query in (r.workman_id or "").lower() or
                        search_query in r.employee_name.lower() or
                        search_query in emp_phone.lower()
                    )
                    if not matches:
                        continue
                filtered_records.append((r, emp_phone))

            self.table.setRowCount(len(filtered_records))
            
            for idx, (r, phone) in enumerate(filtered_records):
                # Set record ID inside checkbox data
                checkbox_item = QTableWidgetItem()
                checkbox_item.setCheckState(Qt.Unchecked)
                checkbox_item.setData(Qt.UserRole, r.id)
                self.table.setItem(idx, 0, checkbox_item)
                
                self.table.setItem(idx, 1, QTableWidgetItem(r.workman_id or ""))
                self.table.setItem(idx, 2, QTableWidgetItem(r.employee_name))
                self.table.setItem(idx, 3, QTableWidgetItem(phone))
                self.table.setItem(idx, 4, QTableWidgetItem(f"{float(r.gross_wages):.2f}"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{float(r.net_wages):.2f}"))
                
                # PDF Status Cell
                status_item = QTableWidgetItem(r.pdf_status)
                if r.pdf_status == "Success":
                    status_item.setForeground(Qt.green)
                elif r.pdf_status == "Failed":
                    status_item.setForeground(Qt.red)
                    status_item.setToolTip(r.pdf_error if r.pdf_error else "")
                self.table.setItem(idx, 6, status_item)
                
                self.table.setItem(idx, 7, QTableWidgetItem(str(r.pdf_attempts)))
                
                sent_str = r.pdf_last_sent.strftime("%d/%m/%Y %H:%M") if r.pdf_last_sent else "Never"
                self.table.setItem(idx, 8, QTableWidgetItem(sent_str))

        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Failed to retrieve payroll history:\n{str(e)}")
        finally:
            session.close()

    def toggle_select_all(self, state):
        """Toggle checked state for all rows currently loaded in the table."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked if state == 2 else Qt.Unchecked)

    def start_batch_sending(self, record_ids):
        """Configure UI layout and spawn background WhatsAppSendWorker thread."""
        if not record_ids:
            QMessageBox.warning(self, "No Records", "No payroll records selected for sending.")
            return

        # Double check settings credentials exist
        from services.whatsapp_service import WhatsAppService
        tester = WhatsAppService()
        if not tester.access_token or not tester.phone_number_id:
            QMessageBox.critical(
                self, "API Config Missing", 
                "WhatsApp API Access Token and Phone Number ID must be configured in Settings first."
            )
            return

        # Double check PDFs are generated
        session = get_session()
        missing_pdfs = []
        for rid in record_ids:
            rec = session.query(PayrollRecord).filter_by(id=rid).first()
            if not rec or not rec.pdf_generated or not rec.pdf_path:
                missing_pdfs.append(rid)
        session.close()

        if missing_pdfs:
            QMessageBox.warning(
                self, "PDF Slips Missing", 
                f"Cannot send. {len(missing_pdfs)} selected records do not have generated PDF slips. "
                f"Please generate them first from the Wage Slips tab."
            )
            return

        # Prepare UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, len(record_ids))
        self.progress_lbl.setVisible(True)
        self.progress_lbl.setText(f"Preparing document uploads for {len(record_ids)} files...")
        
        self.abort_btn.setVisible(True)
        self.send_selected_btn.setEnabled(False)
        self.send_pending_btn.setEnabled(False)
        self.retry_failed_btn.setEnabled(False)

        # Start QThread with type "pdf"
        self.worker = WhatsAppSendWorker(record_ids, send_type="pdf")
        self.worker.progress.connect(self.on_send_progress)
        self.worker.finished.connect(self.on_send_finished)
        self.worker.error.connect(self.on_send_error)
        self.worker.start()

    def on_send_progress(self, current, total, name, success, error_msg):
        """Callback to report progress during background PDF media uploads and message runs."""
        self.progress_bar.setValue(current)
        outcome = "Sent" if success else f"Failed ({error_msg})"
        self.progress_lbl.setText(f"Delivering PDF {current}/{total} to {name}: {outcome}...")
        self.load_records()

    def on_send_finished(self, success_count, failed_count):
        """Callback when batch sending worker finishes execution."""
        QMessageBox.information(
            self, "Sending Complete",
            f"WhatsApp PDF document distribution run complete:\n"
            f"• Successful: {success_count}\n"
            f"• Failed: {failed_count}"
        )
        self.hide_progress()
        self.load_records()
        self.data_changed.emit()

    def on_send_error(self, err_msg):
        """Callback when batch sending thread encounters critical engine failure."""
        QMessageBox.critical(self, "Transmission Aborted", f"A fatal error occurred during PDF transmission:\n{err_msg}")
        self.hide_progress()
        self.load_records()

    def abort_sending(self):
        """Abort background worker processing loop."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.progress_lbl.setText("Aborting transmission batch... finishing current queue...")
            self.abort_btn.setEnabled(False)

    def hide_progress(self):
        """Restore buttons and hide status indicators."""
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        self.abort_btn.setVisible(False)
        self.abort_btn.setEnabled(True)
        self.send_selected_btn.setEnabled(True)
        self.send_pending_btn.setEnabled(True)
        self.retry_failed_btn.setEnabled(True)
        self.worker = None

    def send_selected(self):
        """Gather checked row record IDs and start transmission."""
        record_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                record_id = item.data(Qt.UserRole)
                if record_id:
                    record_ids.append(record_id)
        self.start_batch_sending(record_ids)

    def send_all_pending(self):
        """Query all pending PDF messages for current month and send them."""
        selected_month = self.month_combo.currentText()
        if not selected_month:
            return

        session = get_session()
        try:
            records = (
                session.query(PayrollRecord)
                .filter_by(month_year=selected_month)
                .filter(PayrollRecord.pdf_status != "Success")
                .all()
            )
            record_ids = [r.id for r in records]
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))
            record_ids = []
        finally:
            session.close()

        self.start_batch_sending(record_ids)

    def retry_failed_records(self):
        """Query all failed PDF messages for current month and retry them."""
        selected_month = self.month_combo.currentText()
        if not selected_month:
            return

        session = get_session()
        try:
            records = (
                session.query(PayrollRecord)
                .filter_by(month_year=selected_month)
                .filter_by(pdf_status="Failed")
                .all()
            )
            record_ids = [r.id for r in records]
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))
            record_ids = []
        finally:
            session.close()

        self.start_batch_sending(record_ids)
