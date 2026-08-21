"""Integration and end-to-end tests for the optional Employee ID refactor and migration."""

import io
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import openpyxl
from sqlalchemy import text

# Setup temporary directory for test database
TEMP_DATA_DIR = tempfile.mkdtemp()
os.environ["PAYROLL_DATA_DIR"] = TEMP_DATA_DIR

from database.db import init_database, get_session, run_migrations
from database.models import Employee, PayrollRecord, Setting
from services.payroll_service import PayrollService
from services.pdf_service import PdfService
from services.whatsapp_service import WhatsAppService
from utils.excel_parser import parse_payroll_excel, clean_workman_id
from settings.settings_manager import SettingsManager

from PySide6.QtWidgets import QApplication
from ui.dashboard_tab import DashboardTab
from ui.wageslips_tab import WageSlipsTab
from ui.send_pdf_tab import SendPdfTab
from ui.send_text_tab import SendTextTab
from ui.logs_tab import LogsTab
from ui.upload_tab import UploadTab


def create_mock_excel(rows: list[dict], headers: list[str] = None) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    if headers is None:
        headers = [
            "phone", "month_year", "establishment", "principal_employer", "address",
            "employee_name", "workman_id", "guardian_name", "designation", "uan",
            "bank_account", "wage_period", "attendance", "basic", "da", "allowances",
            "gross_wages", "pf", "esi", "other_deductions", "net_wages", "issue_date"
        ]
    ws.append(headers)
    for r in rows:
        row_data = []
        for h in headers:
            row_data.append(r.get(h, ""))
        ws.append(row_data)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestOptionalWorkmanId(unittest.TestCase):
    """E2E verification of optional Employee ID architecture across parsing, matching, migration, sending, and UI."""

    @classmethod
    def setUpClass(cls):
        # Initialize QApplication singleton for UI tests
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])
        init_database()

    @classmethod
    def tearDownClass(cls):
        from database.db import dispose_engine
        dispose_engine()
        import gc
        gc.collect()
        if os.path.exists(TEMP_DATA_DIR):
            shutil.rmtree(TEMP_DATA_DIR, ignore_errors=True)
        if "PAYROLL_DATA_DIR" in os.environ:
            del os.environ["PAYROLL_DATA_DIR"]

    def setUp(self):
        session = get_session()
        session.query(PayrollRecord).delete()
        session.query(Employee).delete()
        session.query(Setting).delete()
        session.commit()
        session.close()

        # Re-set default configuration
        SettingsManager.set("OPTIONAL_FIELD_PLACEHOLDER", "-")

    def get_base_row(self):
        return {
            "phone": "+919876543210",
            "month_year": "June 2026",
            "month": "June",
            "year": 2026,
            "establishment": "Test Establishment",
            "principal_employer": "Test Employer",
            "address": "Noida, UP",
            "employee_name": "John Doe",
            "workman_id": "EMP101",
            "guardian_name": "Ram Doe",
            "designation": "Analyst",
            "uan": "UAN12345",
            "bank_account": "BANK12345",
            "wage_period": "01/06/2026 to 30/06/2026",
            "attendance": 26.0,
            "basic": 10000.0,
            "da": 2000.0,
            "allowances": 1000.0,
            "gross_wages": 13000.0,
            "pf": 1000.0,
            "esi": 500.0,
            "other_deductions": 500.0,
            "net_wages": 11000.0,
            "issue_date": "29/06/2026"
        }

    def test_scenario_1_backward_compatibility(self):
        """Import Excel where every employee has a valid Employee ID."""
        row = self.get_base_row()
        excel_bytes = create_mock_excel([row])
        
        # Verify parser
        valid, invalid = parse_payroll_excel(excel_bytes)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 0)
        self.assertEqual(valid[0]["workman_id"], "EMP101")
        
        # Verify service commit
        ids = PayrollService.commit_upload(valid)
        self.assertEqual(len(ids), 1)
        
        session = get_session()
        emp = session.query(Employee).first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.workman_id, "EMP101")
        self.assertIsNotNone(emp.employee_uuid)
        
        record = session.query(PayrollRecord).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.employee_id, emp.id)
        self.assertEqual(record.workman_id, "EMP101")
        session.close()

    def test_scenario_2_missing_employee_id_column(self):
        """Import spreadsheet completely omitting workman_id column."""
        row = self.get_base_row()
        del row["workman_id"]
        
        headers = [k for k in row.keys()]
        excel_bytes = create_mock_excel([row], headers=headers)
        
        valid, invalid = parse_payroll_excel(excel_bytes)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 0)
        self.assertIsNone(valid[0]["workman_id"])
        
        ids = PayrollService.commit_upload(valid)
        self.assertEqual(len(ids), 1)
        
        session = get_session()
        emp = session.query(Employee).first()
        self.assertIsNotNone(emp)
        self.assertIsNone(emp.workman_id)
        self.assertIsNotNone(emp.employee_uuid)
        
        record = session.query(PayrollRecord).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.employee_id, emp.id)
        self.assertIsNone(record.workman_id)
        session.close()

    def test_scenario_3_blank_employee_ids(self):
        """Import spreadsheet containing both blank and populated Employee IDs."""
        row_with_id = self.get_base_row()
        row_blank_id = self.get_base_row()
        row_blank_id["employee_name"] = "Alice Smith"
        row_blank_id["phone"] = "+919999999999"
        row_blank_id["workman_id"] = ""
        
        excel_bytes = create_mock_excel([row_with_id, row_blank_id])
        valid, invalid = parse_payroll_excel(excel_bytes)
        self.assertEqual(len(valid), 2)
        
        PayrollService.commit_upload(valid)
        
        session = get_session()
        employees = session.query(Employee).all()
        self.assertEqual(len(employees), 2)
        
        emp1 = session.query(Employee).filter_by(name="John Doe").first()
        emp2 = session.query(Employee).filter_by(name="Alice Smith").first()
        
        self.assertEqual(emp1.workman_id, "EMP101")
        self.assertIsNone(emp2.workman_id)
        self.assertNotEqual(emp1.employee_uuid, emp2.employee_uuid)
        session.close()

    def test_scenario_4_employee_matching_progression(self):
        """Verify fallback matching, stability, and ID updates."""
        # Step 1: Import profile without ID
        row1 = self.get_base_row()
        row1["workman_id"] = ""
        PayrollService.commit_upload([row1])
        
        session = get_session()
        emp = session.query(Employee).filter_by(name="John Doe").first()
        self.assertIsNotNone(emp)
        self.assertIsNone(emp.workman_id)
        uuid_v1 = emp.employee_uuid
        session.close()
        
        # Step 2: Import same employee now WITH an ID
        row2 = self.get_base_row()
        row2["workman_id"] = "EMP101"
        row2["month"] = "July"
        row2["month_year"] = "July 2026"
        row2["wage_period"] = "01/07/2026 to 31/07/2026"
        PayrollService.commit_upload([row2])
        
        session = get_session()
        employees = session.query(Employee).all()
        # Should not create duplicate profiles
        self.assertEqual(len(employees), 1)
        
        emp_updated = employees[0]
        self.assertEqual(emp_updated.workman_id, "EMP101")
        self.assertEqual(emp_updated.employee_uuid, uuid_v1) # stable UUID
        session.close()

    def test_scenario_5_monthly_payroll_uniqueness(self):
        """Verify record updates, additions, and blank-ID safety."""
        # 1. Same employee + same month -> update record
        row1 = self.get_base_row()
        PayrollService.commit_upload([row1])
        
        session = get_session()
        self.assertEqual(session.query(PayrollRecord).count(), 1)
        rec1 = session.query(PayrollRecord).first()
        self.assertEqual(rec1.basic, 10000.0)
        session.close()
        
        # Update same month
        row2 = row1.copy()
        row2["basic"] = 12000.0
        row2["gross_wages"] = 15000.0
        row2["net_wages"] = 13000.0
        PayrollService.commit_upload([row2])
        
        session = get_session()
        self.assertEqual(session.query(PayrollRecord).count(), 1)
        rec_updated = session.query(PayrollRecord).first()
        self.assertEqual(rec_updated.basic, 12000.0)
        session.close()
        
        # 2. Same employee + different month -> create new record
        row3 = row1.copy()
        row3["month"] = "July"
        row3["month_year"] = "July 2026"
        PayrollService.commit_upload([row3])
        session = get_session()
        self.assertEqual(session.query(PayrollRecord).count(), 2)
        session.close()

    def test_scenario_6_database_migration(self):
        """Verify older SQLite schema is correctly upgraded automatically."""
        import sqlite3
        temp_db_fd, temp_db_path = tempfile.mkstemp()
        os.close(temp_db_fd)
        
        # Create OLD schema raw tables
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workman_id VARCHAR UNIQUE NOT NULL,
            name VARCHAR NOT NULL,
            phone VARCHAR NOT NULL,
            designation VARCHAR,
            uan VARCHAR,
            bank_account VARCHAR,
            guardian_name VARCHAR,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME
        )
        """)
        conn.execute("""
        CREATE TABLE payroll_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workman_id VARCHAR NOT NULL REFERENCES employees(workman_id),
            month VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            month_year VARCHAR NOT NULL,
            employee_name VARCHAR NOT NULL,
            gross_wages FLOAT,
            net_wages FLOAT,
            pdf_generated BOOLEAN DEFAULT 0
        )
        """)
        
        # Insert old data
        conn.execute("""
        INSERT INTO employees (id, workman_id, name, phone, designation)
        VALUES (1, 'EMP_OLD_1', 'Old Guy', '9876543210', 'Technician')
        """)
        conn.execute("""
        INSERT INTO payroll_records (id, workman_id, month, year, month_year, employee_name, gross_wages, net_wages)
        VALUES (10, 'EMP_OLD_1', 'June', 2026, 'June 2026', 'Old Guy', 12000.0, 10000.0)
        """)
        conn.commit()
        conn.close()
        
        # Run migrations using SQLAlchemy connection
        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{temp_db_path}")
        with engine.begin() as connection:
            run_migrations(connection)
            
        # Verify migrated schema and data
        conn = sqlite3.connect(temp_db_path)
        
        # Check employees
        cursor = conn.execute("SELECT * FROM employees")
        cols = [description[0] for description in cursor.description]
        self.assertIn("employee_uuid", cols)
        
        emp_row = cursor.fetchone()
        self.assertIsNotNone(emp_row)
        emp_dict = dict(zip(cols, emp_row))
        self.assertEqual(emp_dict["workman_id"], "EMP_OLD_1")
        self.assertIsNotNone(emp_dict["employee_uuid"])
        self.assertEqual(len(emp_dict["employee_uuid"]), 32) # hex UUID
        
        # Check payroll_records
        cursor = conn.execute("SELECT * FROM payroll_records")
        pr_cols = [description[0] for description in cursor.description]
        self.assertIn("employee_id", pr_cols)
        self.assertIn("workman_id", pr_cols)
        
        pr_row = cursor.fetchone()
        self.assertIsNotNone(pr_row)
        pr_dict = dict(zip(pr_cols, pr_row))
        self.assertEqual(pr_dict["employee_id"], 1) # correctly mapped to employees.id
        self.assertEqual(pr_dict["workman_id"], "EMP_OLD_1")
        
        conn.close()
        os.remove(temp_db_path)

    def test_scenario_7_pdf_generation_stability(self):
        """Verify PDF slip generation works with NULL or blank workman_ids."""
        session = get_session()
        emp1 = Employee(workman_id=None, name="No ID Employee", phone="+919876543210")
        session.add(emp1)
        session.commit()
        
        rec = PayrollRecord(
            employee_id=emp1.id,
            workman_id=None,
            month="June",
            year=2026,
            month_year="June 2026",
            employee_name="No ID Employee",
            basic=12000.0,
            gross_wages=12000.0,
            net_wages=12000.0
        )
        session.add(rec)
        session.commit()
        
        record_id = rec.id
        session.close()
        
        # Generate PDF
        pdf_path = PdfService.generate_and_save(record_id)
        self.assertTrue(os.path.exists(pdf_path))
        
        session = get_session()
        rec_after = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertTrue(rec_after.pdf_generated)
        uuid_v1 = rec_after.pdf_uuid
        self.assertIsNotNone(uuid_v1)
        session.close()
        
        # Regenerate PDF (uuid remains stable)
        pdf_path2 = PdfService.generate_and_save(record_id)
        self.assertEqual(pdf_path, pdf_path2)
        
        session = get_session()
        rec_after2 = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertEqual(rec_after2.pdf_uuid, uuid_v1)
        session.close()

    def test_scenario_8_whatsapp_workflow_placeholders(self):
        """Verify message sends gracefully map missing optional parameters to the placeholder."""
        service = WhatsAppService()
        
        # Mock record with blank fields
        class MockRecord:
            month = "June"
            year = 2026
            month_year = "June 2026"
            employee_name = "Amit Kumar"
            workman_id = None
            guardian_name = ""
            designation = "Staff"
            uan = None
            bank_account = "BANK"
            wage_period = "June 2026"
            attendance = 26.0
            basic = 15000.0
            da = 1000.0
            allowances = 500.0
            gross_wages = 16500.0
            pf = 1200.0
            esi = 300.0
            other_deductions = 500.0
            net_wages = 14500.0
            issue_date = "29/06/2026"
            establishment = "ABC Inc"
            principal_employer = "Employer XYZ"
            address = "Noida"
            
        record = MockRecord()
        payload = service.build_template_payload("+919876543210", record)
        params = payload["template"]["components"][0]["parameters"]
        
        # workman_id (index 5) is None -> resolves to placeholder "-"
        self.assertEqual(params[5]["text"], "-")
        # guardian_name (index 6) is "" -> resolves to placeholder "-"
        self.assertEqual(params[6]["text"], "-")
        # uan (index 8) is None -> resolves to placeholder "-"
        self.assertEqual(params[8]["text"], "-")

    def test_scenario_9_gui_integration_smoke_testing(self):
        """Smoke test UI tabs with various Employee ID configurations."""
        session = get_session()
        emp1 = Employee(workman_id="EMP_UI_1", name="Emp One", phone="+919876543211")
        emp2 = Employee(workman_id=None, name="Emp Two", phone="+919876543212")
        emp3 = Employee(workman_id="", name="Emp Three", phone="+919876543213")
        session.add_all([emp1, emp2, emp3])
        session.commit()
        
        # Create payroll records
        rec1 = PayrollRecord(
            employee_id=emp1.id, workman_id="EMP_UI_1", month="June", year=2026,
            month_year="June 2026", employee_name="Emp One", basic=1000.0, gross_wages=1000.0, net_wages=900.0,
            text_attempts=1, text_status="Success", pdf_attempts=1, pdf_status="Failed", pdf_error="API Error"
        )
        rec2 = PayrollRecord(
            employee_id=emp2.id, workman_id=None, month="June", year=2026,
            month_year="June 2026", employee_name="Emp Two", basic=2000.0, gross_wages=2000.0, net_wages=1800.0
        )
        rec3 = PayrollRecord(
            employee_id=emp3.id, workman_id="", month="June", year=2026,
            month_year="June 2026", employee_name="Emp Three", basic=300.0, gross_wages=3000.0, net_wages=2700.0
        )
        session.add_all([rec1, rec2, rec3])
        session.commit()
        session.close()
        
        # Instantiate widgets and verify no AttributeErrors/Crashes on load
        dashboard = DashboardTab()
        dashboard.refresh_dashboard()
        
        wageslips = WageSlipsTab()
        wageslips.refresh_data()
        wageslips.search_input.setText("Emp One")
        wageslips.search_input.setText("") # reset
        
        send_pdf = SendPdfTab()
        send_pdf.refresh_data()
        send_pdf.search_input.setText("EMP_UI_1")
        send_pdf.search_input.setText("") # reset
        
        send_text = SendTextTab()
        send_text.refresh_data()
        send_text.search_input.setText("Emp Two")
        send_text.search_input.setText("") # reset
        
        logs = LogsTab()
        logs.load_logs()
        logs.search_input.setText("Emp") # Matches employee names containing "Emp"
        
        upload = UploadTab()
        upload.reset_ui()
        
        # Assert widgets loaded records
        self.assertGreaterEqual(wageslips.table.rowCount(), 1)
        self.assertGreaterEqual(send_pdf.table.rowCount(), 1)
        self.assertGreaterEqual(send_text.table.rowCount(), 1)
        self.assertGreaterEqual(logs.table.rowCount(), 1)

    def test_scenario_10_regression_verifications(self):
        """Ensure rate limits, template caching, and setting queries operate seamlessly."""
        service = WhatsAppService()
        self.assertIsNotNone(service._rate_limiter)
        self.assertIsNotNone(service._template_cache)
        
        # Verify rate limits don't crash
        service._rate_limiter.acquire()
        service._rate_limiter.report_rate_limit()
        
        # Verify template dictionary defaults
        self.assertEqual(SettingsManager.get("TEMPLATE_NAME", "wageslip"), "wageslip")

    def test_scenario_11_stress_load_performance(self):
        """Verify scale with mixture of empty, blank, and numeric workman_ids."""
        import time
        start_time = time.time()
        
        valid_rows = []
        for i in range(1, 201):
            row = self.get_base_row()
            row["employee_name"] = f"Stress User {i}"
            row["phone"] = f"+91987654{i:06d}"
            
            # Mix IDs
            if i % 4 == 0:
                row["workman_id"] = f"{2000 + i}.0" # numeric float format
            elif i % 4 == 1:
                row["workman_id"] = "N/A" # invalid format
            elif i % 4 == 2:
                row["workman_id"] = "" # empty cell
            else:
                row["workman_id"] = f"EMP_STRESS_{i}" # valid string format
            valid_rows.append(row)
            
        excel_bytes = create_mock_excel(valid_rows)
        valid, invalid = parse_payroll_excel(excel_bytes)
        self.assertEqual(len(valid), 200)
        self.assertEqual(len(invalid), 0)
        
        # Check float normalization
        self.assertEqual(valid[3]["workman_id"], "2004")
        self.assertIsNone(valid[0]["workman_id"]) # N/A -> None
        self.assertIsNone(valid[1]["workman_id"]) # "" -> None
        self.assertEqual(valid[2]["workman_id"], "EMP_STRESS_3")
        
        # Commit upload
        ids = PayrollService.commit_upload(valid)
        self.assertEqual(len(ids), 200)
        
        session = get_session()
        emp_count = session.query(Employee).count()
        pr_count = session.query(PayrollRecord).count()
        session.close()
        
        self.assertEqual(emp_count, 200)
        self.assertEqual(pr_count, 200)
        
        duration = time.time() - start_time
        # Ensure acceptable performance for 200 records (under 5 seconds)
        self.assertLess(duration, 5.0)


if __name__ == "__main__":
    unittest.main()
