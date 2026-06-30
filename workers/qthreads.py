"""PySide6 QThread background workers for asynchronous tasks."""

from PySide6.QtCore import QThread, Signal, QObject
from services.payroll_service import PayrollService
from services.pdf_service import PdfService
from services.whatsapp_service import WhatsAppService


class ExcelParseWorker(QThread):
    """Worker to parse and validate an Excel file without blocking the UI."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            with open(self.file_path, "rb") as f:
                content = f.read()
            result = PayrollService.parse_and_preview(content)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DBSyncWorker(QThread):
    """Worker to commit parsed valid rows to SQLite in the background."""
    finished = Signal(list)  # Emits list of record IDs requiring PDF generation
    error = Signal(str)

    def __init__(self, valid_rows: list):
        super().__init__()
        self.valid_rows = valid_rows

    def run(self):
        try:
            record_ids = PayrollService.commit_upload(self.valid_rows)
            self.finished.emit(record_ids)
        except Exception as e:
            self.error.emit(str(e))


class PdfGenerationWorker(QThread):
    """Worker to batch-generate payslip PDFs in a background thread."""
    progress = Signal(int, int)  # Emits current, total
    finished = Signal(int)       # Emits count generated
    error = Signal(str)

    def __init__(self, record_ids: list[int]):
        super().__init__()
        self.record_ids = record_ids
        self._is_cancelled = False
        self.failures = []

    def cancel(self):
        """Set cancellation flag to abort batch generation at the next iteration."""
        self._is_cancelled = True

    def run(self):
        import logging
        logger = logging.getLogger("PdfGenerationWorker")
        total = len(self.record_ids)
        success_count = 0
        self.failures = []
        for idx, record_id in enumerate(self.record_ids):
            if self._is_cancelled:
                break
            try:
                PdfService.generate_and_save(record_id)
                success_count += 1
            except Exception as e:
                logger.exception("Failed to generate PDF for record ID %d", record_id)
                self.failures.append((record_id, str(e)))
            self.progress.emit(idx + 1, total)
        self.finished.emit(success_count)


class WhatsAppSendWorker(QThread):
    """Worker to batch-send WhatsApp messages (text templates or PDF document messages)."""
    progress = Signal(int, int, str, bool, str)  # Emits current, total, employee_name, success, error_msg
    finished = Signal(int, int)                 # Emits success_count, failed_count
    error = Signal(str)

    def __init__(self, record_ids: list[int], send_type: str):
        """send_type is either 'text' or 'pdf'."""
        super().__init__()
        self.record_ids = record_ids
        self.send_type = send_type
        self._is_cancelled = False

    def cancel(self):
        """Set cancellation flag to abort batch sending at the next iteration."""
        self._is_cancelled = True

    def run(self):
        try:
            # Re-initialize WhatsApp service inside the run thread
            whatsapp_service = WhatsAppService()
            total = len(self.record_ids)
            success_count = 0
            failed_count = 0
            
            from database.db import get_session
            from database.models import PayrollRecord
            
            for idx, record_id in enumerate(self.record_ids):
                if self._is_cancelled:
                    break
                
                # Fetch employee name for reporting progress
                session = get_session()
                try:
                    record = session.query(PayrollRecord).filter_by(id=record_id).first()
                    emp_name = record.employee_name if record else f"Record ID {record_id}"
                finally:
                    session.close()

                try:
                    if self.send_type == "text":
                        success, err = whatsapp_service.send_text_with_retry_and_db_logging(record_id)
                    else:
                        success, err = whatsapp_service.send_pdf_with_retry_and_db_logging(record_id)
                except Exception as ex:
                    success = False
                    err = f"Unexpected thread exception: {str(ex)}"

                if success:
                    success_count += 1
                else:
                    failed_count += 1

                self.progress.emit(idx + 1, total, emp_name, success, err)
                
            self.finished.emit(success_count, failed_count)
        except Exception as e:
            self.error.emit(str(e))


class ConnectionTestWorker(QThread):
    """Worker to perform connection and credential testing asynchronously."""
    finished = Signal(bool, str)
    error = Signal(str)

    def run(self):
        try:
            whatsapp_service = WhatsAppService()
            success, msg = whatsapp_service.validate_credentials()
            self.finished.emit(success, msg)
        except Exception as e:
            self.error.emit(str(e))
