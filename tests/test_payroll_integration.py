"""Integration tests for dynamic payroll multi-year support, updates, and unique constraints."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal

# Set test environment directory before loading database connection
TEMP_DATA_DIR = tempfile.mkdtemp()
os.environ["PAYROLL_DATA_DIR"] = TEMP_DATA_DIR

from database.db import init_database, get_session
from database.models import Employee, PayrollRecord
from services.payroll_service import PayrollService
from sqlalchemy.exc import IntegrityError


class TestPayrollIntegration(unittest.TestCase):
    """Verifies multi-year co-existence, repeated uploads, and constraint safety."""

    @classmethod
    def setUpClass(cls):
        # Initialize DB in our temporary directory
        init_database()

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary directory
        from database.db import dispose_engine
        dispose_engine()
        import gc
        gc.collect()
        if os.path.exists(TEMP_DATA_DIR):
            shutil.rmtree(TEMP_DATA_DIR, ignore_errors=True)
        if "PAYROLL_DATA_DIR" in os.environ:
            del os.environ["PAYROLL_DATA_DIR"]

    def setUp(self):
        # Clean database tables before each test
        session = get_session()
        session.query(PayrollRecord).delete()
        session.query(Employee).delete()
        session.commit()
        session.close()

    def test_multiple_years_coexistence_for_same_employee(self):
        # Prepare 5 years of payroll data for the same employee
        employee_data = []
        for year in range(2026, 2031):
            employee_data.append({
                "workman_id": "EMP_TEST_01",
                "employee_name": "Test Employee 1",
                "phone": "+919999999999",
                "designation": "Staff",
                "uan": "UAN12345",
                "bank_account": "BANK12345",
                "guardian_name": "Guardian",
                "month": "June",
                "year": year,
                "month_year": f"June {year}",
                "establishment": "Test Est",
                "principal_employer": "Test Employer",
                "address": "Test Address",
                "wage_period": f"01/06/{year} to 30/06/{year}",
                "attendance": 26.0,
                "basic": 10000.0,
                "da": 2000.0,
                "allowances": 1000.0,
                "gross_wages": 13000.0,
                "pf": 1000.0,
                "esi": 500.0,
                "other_deductions": 500.0,
                "net_wages": 11000.0,
                "issue_date": f"29/06/{year}"
            })

        # Commit upload
        PayrollService.commit_upload(employee_data)

        # Query database and verify
        session = get_session()
        employees = session.query(Employee).all()
        records = session.query(PayrollRecord).all()
        session.close()

        # Should only create 1 Employee profile
        self.assertEqual(len(employees), 1)
        self.assertEqual(employees[0].workman_id, "EMP_TEST_01")

        # Should create 5 Payroll Records, one for each year
        self.assertEqual(len(records), 5)
        
        years_found = [r.year for r in records]
        self.assertEqual(sorted(years_found), [2026, 2027, 2028, 2029, 2030])

    def test_repeated_uploads_update_existing_records(self):
        # Upload initial record for June 2026
        row_v1 = {
            "workman_id": "EMP_UPDATE_01",
            "employee_name": "Update Employee",
            "phone": "+919999999998",
            "designation": "Staff",
            "uan": "UAN12345",
            "bank_account": "BANK12345",
            "guardian_name": "Guardian",
            "month": "June",
            "year": 2026,
            "month_year": "June 2026",
            "establishment": "Test Est",
            "principal_employer": "Test Employer",
            "address": "Test Address",
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
        
        PayrollService.commit_upload([row_v1])
        
        session = get_session()
        record_before = session.query(PayrollRecord).filter_by(workman_id="EMP_UPDATE_01").first()
        self.assertIsNotNone(record_before)
        self.assertEqual(record_before.net_wages, 11000.0)
        session.close()

        # Upload updated record (same workman_id and period, but updated net wages)
        row_v2 = row_v1.copy()
        row_v2["basic"] = 12000.0
        row_v2["gross_wages"] = 15000.0
        row_v2["net_wages"] = 13000.0
        
        PayrollService.commit_upload([row_v2])

        session = get_session()
        records_after = session.query(PayrollRecord).filter_by(workman_id="EMP_UPDATE_01").all()
        session.close()

        # Verify that NO duplicate row was created (count remains 1)
        self.assertEqual(len(records_after), 1)
        
        # Verify that wages were successfully updated
        self.assertEqual(records_after[0].net_wages, 13000.0)
        self.assertEqual(records_after[0].basic, 12000.0)

    def test_database_unique_constraint_enforcement(self):
        # Setup an employee record manually
        session = get_session()
        emp = Employee(workman_id="EMP_UNIQUE_01", name="Unique Employee", phone="+919999999997")
        session.add(emp)
        session.commit()
        
        # Insert first record
        rec1 = PayrollRecord(
            employee_id=emp.id,
            workman_id="EMP_UNIQUE_01",
            month="June",
            year=2026,
            month_year="June 2026",
            employee_name="Unique Employee",
            net_wages=10000.0,
            gross_wages=12000.0
        )
        session.add(rec1)
        session.commit()
        
        # Attempt to insert duplicate record with same (employee_id, month, year)
        rec2 = PayrollRecord(
            employee_id=emp.id,
            workman_id="EMP_UNIQUE_01",
            month="June",
            year=2026,
            month_year="June 2026",
            employee_name="Unique Employee",
            net_wages=11000.0,
            gross_wages=13000.0
        )
        session.add(rec2)
        
        # Must raise IntegrityError due to the UniqueConstraint on sqlite level
        with self.assertRaises(IntegrityError):
            session.commit()
            
        session.rollback()
        session.close()


if __name__ == "__main__":
    unittest.main()
