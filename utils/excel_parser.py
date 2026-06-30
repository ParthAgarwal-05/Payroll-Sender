"""Excel parser for the 22-column payroll format."""

import io
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_month_year(val: Any) -> tuple[str, int] | None:
    """Parse month_year from string or date object into (month_name, year).

    Supported formats:
    - Date or datetime object
    - String like "06/2026", "06-2026", "June 2026", "June-2026"
    """
    if isinstance(val, (datetime, date)):
        english_months = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        return english_months[val.month], val.year

    if not val:
        return None

    s = str(val).strip()
    
    # Try MM/YYYY or MM-YYYY
    match = re.match(r"^(\d{1,2})[/-](\d{4})$", s)
    if match:
        m_num = int(match.group(1))
        year = int(match.group(2))
        month_map = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
        if m_num in month_map:
            return month_map[m_num], year

    # Try "Month YYYY" or "Month-YYYY"
    match = re.match(r"^([a-zA-Z]+)[ -](\d{4})$", s)
    if match:
        m_name = match.group(1).capitalize()
        year = int(match.group(2))
        valid_months = {
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        }
        if m_name in valid_months:
            return m_name, year

    return None


def clean_phone(val: Any) -> str | None:
    """Normalize phone number format for WhatsApp.

    Adds + prefix if missing, cleans non-digits, and validates 10-15 digits.
    """
    if val is None:
        return None
    
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s:
        return None

    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)

    if not digits:
        return None

    if not has_plus:
        if len(digits) == 10:
            return f"+91{digits}"  # Default to India country code if 10 digits
        return f"+{digits}"
    
    return f"+{digits}"


def parse_date_str(val: Any) -> str | None:
    """Parse date or date string into a clean DD/MM/YYYY string."""
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y")
    
    if not val:
        return None
    
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
            
    return s


def parse_payroll_excel(file_bytes: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse and validate payroll records from an uploaded Excel file.

    Expected columns in row 1:
        phone, month_year, establishment, principal_employer, address, employee_name,
        workman_id, guardian_name, designation, uan, bank_account, wage_period,
        attendance, basic, da, allowances, gross_wages, pf, esi, other_deductions,
        net_wages, issue_date

    Returns:
        A tuple (valid_rows, invalid_rows)
    """
    valid_rows = []
    invalid_rows = []
    seen_employees = set()

    try:
        import openpyxl
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = workbook.active
        if not sheet:
            return [], [{"row": 0, "error": "No active worksheet found in workbook"}]
    except Exception as e:
        return [], [{"row": 0, "error": f"Failed to open Excel workbook: {str(e)}"}]

    headers = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in sheet[1]]

    expected_cols = [
        "phone", "month_year", "establishment", "principal_employer", "address",
        "employee_name", "workman_id", "guardian_name", "designation", "uan",
        "bank_account", "wage_period", "attendance", "basic", "da", "allowances",
        "gross_wages", "pf", "esi", "other_deductions", "net_wages", "issue_date"
    ]

    header_mapping = {}
    for col in expected_cols:
        if col in headers:
            header_mapping[col] = headers.index(col)
        else:
            header_mapping[col] = -1

    missing = [col for col in expected_cols if header_mapping[col] == -1]
    if missing:
        return [], [{"row": 1, "error": f"Missing required columns: {', '.join(missing)}"}]

    for row_num in range(2, sheet.max_row + 1):
        row = sheet[row_num]
        if all(cell.value is None for cell in row):
            continue

        row_data = {}
        errors = []

        string_fields = [
            "establishment", "principal_employer", "address", "employee_name",
            "workman_id", "guardian_name", "designation", "uan", "bank_account",
            "wage_period"
        ]
        for field in string_fields:
            val = row[header_mapping[field]].value
            if val is None or str(val).strip() == "":
                errors.append(f"{field.replace('_', ' ').capitalize()} is required")
                row_data[field] = ""
            else:
                row_data[field] = str(val).strip()

        # Read phone and clean
        phone_val = row[header_mapping["phone"]].value
        cleaned_phone = clean_phone(phone_val)
        if not cleaned_phone:
            errors.append("Valid Phone number is required")
            row_data["phone"] = str(phone_val) if phone_val is not None else ""
        else:
            digits = re.sub(r"\D", "", cleaned_phone[1:])
            if len(digits) < 10 or len(digits) > 15:
                errors.append("Phone number must have 10-15 digits after country code")
            row_data["phone"] = cleaned_phone

        # Read month_year
        my_val = row[header_mapping["month_year"]].value
        parsed_my = parse_month_year(my_val)
        if not parsed_my:
            errors.append("Month year is required and must be in MM/YYYY or Month YYYY format")
            row_data["month_year"] = str(my_val) if my_val is not None else ""
        else:
            month_name, year_val = parsed_my
            row_data["month_year"] = f"{month_name} {year_val}"
            row_data["month"] = month_name
            row_data["year"] = year_val
            
            # Check for duplicate employee record within the same Excel sheet
            if "workman_id" in row_data and row_data["workman_id"]:
                dup_key = (row_data["workman_id"].strip().upper(), month_name, year_val)
                if dup_key in seen_employees:
                    errors.append("Duplicate employee entry for the same month/year in sheet")
                else:
                    seen_employees.add(dup_key)

        # Read attendance
        att_val = row[header_mapping["attendance"]].value
        try:
            if att_val is None or str(att_val).strip() == "":
                errors.append("Attendance is required")
                row_data["attendance"] = 0.0
            else:
                row_data["attendance"] = float(str(att_val).strip())
                if row_data["attendance"] < 0:
                    errors.append("Attendance cannot be negative")
        except ValueError:
            errors.append("Attendance must be a valid number")
            row_data["attendance"] = 0.0

        # Read issue_date
        id_val = row[header_mapping["issue_date"]].value
        parsed_id = parse_date_str(id_val)
        if not parsed_id:
            errors.append("Issue date is required")
            row_data["issue_date"] = ""
        else:
            row_data["issue_date"] = parsed_id

        decimal_fields = [
            "basic", "da", "allowances", "gross_wages", "pf", "esi",
            "other_deductions", "net_wages"
        ]
        for field in decimal_fields:
            val = row[header_mapping[field]].value
            try:
                if val is None or str(val).strip() == "":
                    if field in ("da", "allowances", "pf", "esi", "other_deductions"):
                        row_data[field] = Decimal("0")
                    else:
                        errors.append(f"{field.replace('_', ' ').capitalize()} is required")
                        row_data[field] = Decimal("0")
                else:
                    row_data[field] = Decimal(str(val).strip())
            except (InvalidOperation, ValueError):
                errors.append(f"{field.replace('_', ' ').capitalize()} must be a valid number")
                row_data[field] = Decimal("0")

        if "gross_wages" in row_data and row_data["gross_wages"] <= 0:
            errors.append("Gross wages must be greater than zero")

        if "net_wages" in row_data and row_data["net_wages"] <= 0:
            errors.append("Net wages must be greater than zero")

        for field in ("pf", "esi", "other_deductions"):
            if field in row_data and row_data[field] < 0:
                errors.append(f"{field.upper().replace('_', ' ')} cannot be negative")

        if all(f in row_data for f in ("gross_wages", "net_wages", "pf", "esi", "other_deductions")):
            total_ded = row_data["pf"] + row_data["esi"] + row_data["other_deductions"]
            row_data["total_deductions"] = total_ded
            expected_net = row_data["gross_wages"] - total_ded
            if abs(expected_net - row_data["net_wages"]) > Decimal("0.01"):
                errors.append(
                    f"Net wages inconsistency: Gross ({row_data['gross_wages']}) - "
                    f"Deductions ({total_ded}) must equal Net ({row_data['net_wages']})"
                )

        # Formatting values for JSON/Preview output
        row_data_serialized = {}
        for k, v in row_data.items():
            if isinstance(v, Decimal):
                row_data_serialized[k] = float(v)
            else:
                row_data_serialized[k] = v

        if errors:
            invalid_rows.append({
                "row": row_num,
                "data": row_data_serialized,
                "error": "; ".join(errors),
            })
        else:
            valid_rows.append(row_data_serialized)

    return valid_rows, invalid_rows
