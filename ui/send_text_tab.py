"""Send Text Messages tab for distributing payslips via template WhatsApp messages."""

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


class SendTextTab(QWidget):
    """View to select and send template-based text wage slips via WhatsApp Cloud API."""
    
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
        title_lbl = QLabel("Send Text Messages")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Distribute payroll wage slips using WhatsApp pre-approved templates.")
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
        
        # Debounce database searches to prevent UI lagging on keystrokes
        from PySide6.QtCore import QTimer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.load_records)
        self.search_input.textChanged.connect(self.search_timer.start)
        
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
            "Text Status", "Attempts", "Last Sent"
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
        # Prevent loading if worker is running
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
            from sqlalchemy.orm import joinedload
            records = (
                session.query(PayrollRecord)
                .options(joinedload(PayrollRecord.employee))
                .filter_by(month_year=selected_month)
                .all()
            )
            
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
                # Set record ID inside custom data property or item cell
                checkbox_item = QTableWidgetItem()
                checkbox_item.setCheckState(Qt.Unchecked)
                checkbox_item.setData(Qt.UserRole, r.id)  # Save record_id
                self.table.setItem(idx, 0, checkbox_item)
                
                self.table.setItem(idx, 1, QTableWidgetItem(r.workman_id or ""))
                self.table.setItem(idx, 2, QTableWidgetItem(r.employee_name))
                self.table.setItem(idx, 3, QTableWidgetItem(phone))
                self.table.setItem(idx, 4, QTableWidgetItem(f"{float(r.gross_wages):.2f}"))
                self.table.setItem(idx, 5, QTableWidgetItem(f"{float(r.net_wages):.2f}"))
                
                # Status Cell
                status_item = QTableWidgetItem(r.text_status)
                if r.text_status == "Success":
                    status_item.setForeground(Qt.green)
                elif r.text_status == "Failed":
                    status_item.setForeground(Qt.red)
                    status_item.setToolTip(r.text_error if r.text_error else "")
                self.table.setItem(idx, 6, status_item)
                
                self.table.setItem(idx, 7, QTableWidgetItem(str(r.text_attempts)))
                
                sent_str = r.text_last_sent.strftime("%d/%m/%Y %H:%M") if r.text_last_sent else "Never"
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

        # Prepare UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, len(record_ids))
        self.progress_lbl.setVisible(True)
        self.progress_lbl.setText(f"Preparing transmission for {len(record_ids)} messages...")
        
        self.abort_btn.setVisible(True)
        self.send_selected_btn.setEnabled(False)
        self.send_pending_btn.setEnabled(False)
        self.retry_failed_btn.setEnabled(False)

        # Start QThread
        self.current_batch_ids = record_ids
        self.worker = WhatsAppSendWorker(record_ids, send_type="text")
        self.worker.progress.connect(self.on_send_progress)
        self.worker.finished.connect(self.on_send_finished)
        self.worker.error.connect(self.on_send_error)
        self.worker.start()

    def on_send_progress(self, current, total, name, success, error_msg):
        """Callback to report individual message status during background transmission."""
        self.progress_bar.setValue(current)
        outcome = "Sent" if success else f"Failed ({error_msg})"
        self.progress_lbl.setText(f"Sending message {current}/{total} to {name}: {outcome}...")
        
        # Partially update the affected row to avoid heavy full table rebuild
        if hasattr(self, "current_batch_ids") and len(self.current_batch_ids) >= current:
            rec_id = self.current_batch_ids[current - 1]
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.UserRole) == rec_id:
                    # Update status cell
                    status_text = "Success" if success else "Failed"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(Qt.green if success else Qt.red)
                    if not success:
                        status_item.setToolTip(error_msg)
                    self.table.setItem(row, 6, status_item)

                    # Update attempts cell
                    att_item = self.table.item(row, 7)
                    if att_item:
                        try:
                            attempts = int(att_item.text()) + 1
                            att_item.setText(str(attempts))
                        except ValueError:
                            pass
                    
                    # Update last sent cell
                    from datetime import datetime
                    sent_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                    sent_item = self.table.item(row, 8)
                    if sent_item:
                        sent_item.setText(sent_str)
                    else:
                        self.table.setItem(row, 8, QTableWidgetItem(sent_str))
                    break

    def on_send_finished(self, success_count, failed_count):
        """Callback when batch sending worker finishes execution."""
        QMessageBox.information(
            self, "Sending Complete",
            f"WhatsApp text distribution run complete:\n"
            f"• Successful: {success_count}\n"
            f"• Failed: {failed_count}"
        )
        self.hide_progress()
        self.load_records()
        self.data_changed.emit()

    def on_send_error(self, err_msg):
        """Callback when batch sending thread encounters critical engine failure."""
        QMessageBox.critical(self, "Transmission Aborted", f"A fatal error occurred during batch transmission:\n{err_msg}")
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
        """Query all pending text messages for current month and send them."""
        selected_month = self.month_combo.currentText()
        if not selected_month:
            return

        session = get_session()
        try:
            records = (
                session.query(PayrollRecord)
                .filter_by(month_year=selected_month)
                .filter(PayrollRecord.text_status != "Success")
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
        """Query all failed text messages for current month and retry them."""
        selected_month = self.month_combo.currentText()
        if not selected_month:
            return

        session = get_session()
        try:
            records = (
                session.query(PayrollRecord)
                .filter_by(month_year=selected_month)
                .filter_by(text_status="Failed")
                .all()
            )
            record_ids = [r.id for r in records]
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))
            record_ids = []
        finally:
            session.close()

        self.start_batch_sending(record_ids)

    def cleanup_workers(self):
        """Stop and join any active sending workers."""
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
