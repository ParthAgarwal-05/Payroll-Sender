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


if __name__ == "__main__":
    unittest.main()
