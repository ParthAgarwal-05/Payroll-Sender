"""Unit tests for the ReportLab Form VIII-C PDF generation service."""

import unittest
from services.pdf_service import generate_wage_slip


class MockPayrollRecord:
    """Mock database model payroll record for testing."""
    def __init__(self):
        self.issue_date = "29/06/2026"
        self.establishment = "ABC ESTABLISHMENT"
        self.principal_employer = "JOHN SMITH"
        self.address = "123 STREET RD, IN"
        self.employee_name = "Jane Doe"
        self.guardian_name = "Father Doe"
        self.designation = "Associate Manager"
        self.uan = "UAN10099"
        self.bank_account = "BANK990011"
        self.wage_period = "01/06/2026 to 30/06/2026"
        self.workman_id = "EMP900"
        self.basic = 15000.0
        self.da = 1000.0
        self.allowances = 500.0
        self.attendance = 26.0
        self.gross_wages = 16500.0
        self.pf = 1200.0
        self.esi = 300.0
        self.other_deductions = 500.0
        self.net_wages = 14500.0


class TestPdfService(unittest.TestCase):
    """Verifies that the PDF generator generates binary document data from the record layout."""

    def test_pdf_generation_content_size(self):
        record = MockPayrollRecord()
        company_info = {
            "name": record.establishment,
            "address": record.address,
        }
        
        pdf_bytes = generate_wage_slip(record, company_info)
        
        # Verify we receive non-empty PDF bytes
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)  # Standard reportlab PDF header/trailer is > 1KB
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))  # PDF signature check


class TestPdfUuidStorage(unittest.TestCase):
    """Verifies that PDFs are stored using unique record UUIDs, which are immutable once generated."""

    @classmethod
    def setUpClass(cls):
        import os
        import tempfile
        # Configure a temporary database directory
        cls.temp_dir = tempfile.mkdtemp()
        os.environ["PAYROLL_DATA_DIR"] = cls.temp_dir
        
        from database.db import init_database
        init_database()

    @classmethod
    def tearDownClass(cls):
        import os
        import shutil
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
        if "PAYROLL_DATA_DIR" in os.environ:
            del os.environ["PAYROLL_DATA_DIR"]

    def setUp(self):
        from database.db import get_session
        from database.models import Employee, PayrollRecord
        session = get_session()
        session.query(PayrollRecord).delete()
        session.query(Employee).delete()
        session.commit()
        session.close()

    def test_uuid_generation_on_first_save_and_regeneration_reuse(self):
        import os
        from database.db import get_session
        from database.models import Employee, PayrollRecord
        from services.pdf_service import PdfService

        # 1. Create a dummy employee and payroll record with pdf_uuid=None
        session = get_session()
        emp = Employee(workman_id="EMP_TEST_UUID", name="Test UUID Employee", phone="+919876543210")
        session.add(emp)
        session.commit()

        record = PayrollRecord(
            workman_id="EMP_TEST_UUID",
            employee_name="Test UUID Employee",
            month="June",
            year=2026,
            month_year="June 2026",
            pdf_generated=False,
            pdf_uuid=None
        )
        session.add(record)
        session.commit()
        record_id = record.id
        session.close()

        # 2. Generate and save PDF (triggers UUID generation)
        pdf_path = PdfService.generate_and_save(record_id)

        # 3. Verify UUID is generated and saved in DB
        session = get_session()
        record = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertIsNotNone(record.pdf_uuid)
        self.assertTrue(len(record.pdf_uuid) == 32)  # uuid4 hex length is 32

        # 4. Verify filename on disk uses the UUID
        expected_filename = f"{record.pdf_uuid}.pdf"
        self.assertTrue(pdf_path.endswith(expected_filename))
        self.assertTrue(os.path.exists(pdf_path))
        
        # Keep track of first generated UUID and path
        first_uuid = record.pdf_uuid
        first_path = pdf_path
        session.close()

        # 5. Regenerate PDF and verify UUID remains identical and path is overwritten
        pdf_path_2 = PdfService.generate_and_save(record_id)
        
        session = get_session()
        record = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertEqual(record.pdf_uuid, first_uuid)
        self.assertEqual(pdf_path_2, first_path)
        self.assertTrue(os.path.exists(pdf_path_2))
        session.close()


if __name__ == "__main__":
    unittest.main()
