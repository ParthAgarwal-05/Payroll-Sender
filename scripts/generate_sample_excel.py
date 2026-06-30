"""Helper script to generate a sample 22-column payroll Excel sheet with valid and invalid records."""

import openpyxl


def generate_sample():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Payroll Data"

    headers = [
        "phone", "month_year", "establishment", "principal_employer", "address",
        "employee_name", "workman_id", "guardian_name", "designation", "uan",
        "bank_account", "wage_period", "attendance", "basic", "da", "allowances",
        "gross_wages", "pf", "esi", "other_deductions", "net_wages", "issue_date"
    ]
    ws.append(headers)

    # Row 1: Valid Employee (India code, correct math: 20000 gross, 2200 deductions, 17800 net)
    ws.append([
        "9876543210", "January 2026", "GALAXY SERVICES LTD", "ALEX JONES", "SECTOR 62, NOIDA",
        "Amit Kumar", "EMP001", "Ram Kumar", "Technical Analyst", "UAN100998877",
        "A/C 502000998811", "01/01/2026 to 31/01/2026", "26.0", "15000", "3000", "2000",
        "20000", "1500", "300", "400", "17800", "29/01/2026"
    ])

    # Row 2: Valid Employee (Already has country code +91, correct math: 15000 gross, 1600 deductions, 13400 net)
    ws.append([
        "+918888888888", "January 2026", "GALAXY SERVICES LTD", "ALEX JONES", "SECTOR 62, NOIDA",
        "Siddharth Sharma", "EMP002", "Vijay Sharma", "Operator", "UAN100998855",
        "A/C 502000998822", "01/01/2026 to 31/01/2026", "25.5", "10000", "2000", "3000",
        "15000", "1000", "200", "400", "13400", "29/01/2026"
    ])

    # Row 3: INVALID Employee (Math error: 18000 gross, 1800 deductions, but net is written as 12000 instead of 16200)
    ws.append([
        "7777777777", "January 2026", "GALAXY SERVICES LTD", "ALEX JONES", "SECTOR 62, NOIDA",
        "Priya Patel", "EMP003", "Kishore Patel", "Developer", "UAN100998833",
        "A/C 502000998833", "01/01/2026 to 31/01/2026", "26.0", "12000", "4000", "2000",
        "18000", "1200", "200", "400", "12000", "29/01/2026"
    ])

    # Row 4: INVALID Employee (Phone number format is wrong and Net Wages are missing)
    ws.append([
        "123", "January 2026", "GALAXY SERVICES LTD", "ALEX JONES", "SECTOR 62, NOIDA",
        "Rahul Singh", "EMP004", "Jaswant Singh", "Helper", "UAN100998844",
        "A/C 502000998844", "01/01/2026 to 31/01/2026", "20.0", "8000", "1000", "1000",
        "10000", "800", "200", "0", "", "29/01/2026"
    ])

    wb.save("sample_payroll.xlsx")
    print("Generated sample_payroll.xlsx successfully in project directory.")


if __name__ == "__main__":
    generate_sample()
