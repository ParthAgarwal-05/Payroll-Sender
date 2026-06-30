"""Service for stateful payroll upload, employee synchronization, and record tracking."""

from pathlib import Path
from datetime import datetime
from database.db import get_session
from database.models import Employee, PayrollRecord
from utils.excel_parser import parse_payroll_excel
from services.pdf_service import PdfService
from utils.logger_config import setup_logger

logger = setup_logger("PayrollService")


class PayrollService:
    """Orchestrates Excel parsing, previews, synchronization commits, and PDF regeneration trigger checks."""

    @staticmethod
    def parse_and_preview(file_bytes: bytes) -> dict:
        """Parse Excel file bytes and return a structure suitable for the GUI preview table.

        Does not modify the database.
        """
        valid_rows, invalid_rows = parse_payroll_excel(file_bytes)
        
        # Calculate summary statistics
        total_gross = 0.0
        total_deductions = 0.0
        total_net = 0.0
        
        preview_rows = []
        
        # Format valid rows for preview
        for row in valid_rows:
            preview_rows.append({
                "is_valid": True,
                "row_number": None,  # Will be set in UI or loop
                "workman_id": row.get("workman_id", ""),
                "employee_name": row.get("employee_name", ""),
                "phone": row.get("phone", ""),
                "month_year": row.get("month_year", ""),
                "gross_wages": row.get("gross_wages", 0.0),
                "net_wages": row.get("net_wages", 0.0),
                "errors": [],
                "raw_data": row
            })
            total_gross += float(row.get("gross_wages", 0.0))
            total_deductions += float(row.get("total_deductions", 0.0))
            total_net += float(row.get("net_wages", 0.0))
            
        # Format invalid rows for preview
        for item in invalid_rows:
            preview_rows.append({
                "is_valid": False,
                "row_number": item.get("row", 0),
                "workman_id": item.get("data", {}).get("workman_id", ""),
                "employee_name": item.get("data", {}).get("employee_name", ""),
                "phone": item.get("data", {}).get("phone", ""),
                "month_year": item.get("data", {}).get("month_year", ""),
                "gross_wages": item.get("data", {}).get("gross_wages", 0.0),
                "net_wages": item.get("data", {}).get("net_wages", 0.0),
                "errors": item.get("error", "").split("; "),
                "raw_data": item.get("data", {})
            })

        return {
            "valid_count": len(valid_rows),
            "invalid_count": len(invalid_rows),
            "preview_data": preview_rows,
            "total_gross": total_gross,
            "total_deductions": total_deductions,
            "total_net": total_net,
            "raw_valid_rows": valid_rows  # Keep to pass into commit function
        }

    @staticmethod
    def commit_upload(valid_rows: list[dict]) -> list[int]:
        """Commit parsed valid rows to the database.

        Updates employee profiles, inserts/updates payroll records, and
        returns a list of payroll record IDs that require PDF generation.
        """
        from sqlalchemy import func
        from utils.excel_parser import clean_workman_id

        session = get_session()
        record_ids_to_generate = []
        processed_in_batch = set()
        try:
            for row in valid_rows:
                workman_id_raw = row.get("workman_id")
                workman_id_clean = clean_workman_id(workman_id_raw)
                month = row["month"]
                year = row["year"]

                name = row["employee_name"]
                phone = row["phone"]
                designation = row["designation"]
                uan = row["uan"]
                bank_account = row["bank_account"]
                guardian_name = row["guardian_name"]
                
                # 1. Sync Employee Profile
                from utils.phone_utils import normalize_phone
                phone_normalized, phone_valid, _ = normalize_phone(phone)
                
                employee = None
                if workman_id_clean:
                    employee = session.query(Employee).filter(
                        func.upper(Employee.workman_id) == workman_id_clean.upper()
                    ).first()

                if not employee:
                    # Match by name and normalized phone
                    candidates = session.query(Employee).filter(
                        func.upper(Employee.name) == name.strip().upper()
                    ).all()
                    
                    for cand in candidates:
                        cand_norm, cand_valid, _ = normalize_phone(cand.phone)
                        if phone_valid and cand_valid and cand_norm == phone_normalized:
                            employee = cand
                            break
                        elif not phone_valid and not cand_valid and cand.phone.strip() == phone.strip():
                            employee = cand
                            break

                    if employee and workman_id_clean:
                        if employee.workman_id and clean_workman_id(employee.workman_id):
                            # Employee already has a different workman_id, do NOT merge
                            employee = None
                        else:
                            # Update employee's workman_id
                            employee.workman_id = workman_id_clean

                if not employee:
                    employee = Employee(
                        workman_id=workman_id_clean,
                        name=name,
                        phone=phone,
                        designation=designation,
                        uan=uan,
                        bank_account=bank_account,
                        guardian_name=guardian_name,
                        is_deleted=False
                    )
                    session.add(employee)
                else:
                    # Update fields if changed
                    if employee.name != name: employee.name = name
                    if employee.phone != phone: employee.phone = phone
                    if employee.designation != designation: employee.designation = designation
                    if employee.uan != uan: employee.uan = uan
                    if employee.bank_account != bank_account: employee.bank_account = bank_account
                    if employee.guardian_name != guardian_name: employee.guardian_name = guardian_name
                    employee.is_deleted = False
                
                session.flush()

                # Deduplicate batch uploads using employee.id
                batch_key = (employee.id, month, year)
                if batch_key in processed_in_batch:
                    logger.warning("Duplicate record in batch ignored: Employee %s, Period %s/%s", employee.id, month, year)
                    continue
                processed_in_batch.add(batch_key)

                # 2. Sync Payroll Record
                record = session.query(PayrollRecord).filter_by(
                    employee_id=employee.id, month=month, year=year
                ).first()
                
                # Prepare numeric comparisons & assignments
                payroll_data = {
                    "establishment": row.get("establishment"),
                    "principal_employer": row.get("principal_employer"),
                    "address": row.get("address"),
                    "employee_name": name,
                    "guardian_name": guardian_name,
                    "designation": designation,
                    "uan": uan,
                    "bank_account": bank_account,
                    "wage_period": row.get("wage_period"),
                    "attendance": float(row.get("attendance", 0.0)),
                    "basic": float(row.get("basic", 0.0)),
                    "da": float(row.get("da", 0.0)),
                    "allowances": float(row.get("allowances", 0.0)),
                    "gross_wages": float(row.get("gross_wages", 0.0)),
                    "pf": float(row.get("pf", 0.0)),
                    "esi": float(row.get("esi", 0.0)),
                    "other_deductions": float(row.get("other_deductions", 0.0)),
                    "net_wages": float(row.get("net_wages", 0.0)),
                    "issue_date": row.get("issue_date"),
                }
                
                needs_pdf_gen = False
                
                if not record:
                    # Create new payroll record
                    record = PayrollRecord(
                        employee_id=employee.id,
                        workman_id=workman_id_clean,
                        month=month,
                        year=year,
                        month_year=row["month_year"],
                        pdf_generated=False,
                        text_status="Pending",
                        pdf_status="Pending",
                        **payroll_data
                    )
                    session.add(record)
                    needs_pdf_gen = True
                else:
                    # Check if any values changed to trigger PDF regeneration
                    changed = False
                    if record.workman_id != workman_id_clean:
                        record.workman_id = workman_id_clean
                        changed = True
                    for k, v in payroll_data.items():
                        old_v = getattr(record, k)
                        if old_v != v:
                            setattr(record, k, v)
                            changed = True
                    
                    if changed or not record.pdf_generated or not record.pdf_path:
                        record.pdf_generated = False
                        needs_pdf_gen = True
                
                session.flush()
                if needs_pdf_gen:
                    record_ids_to_generate.append(record.id)
            
            session.commit()
            return record_ids_to_generate
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def delete_payroll_record(record_id: int) -> None:
        """Delete only the month's payroll record. Employee profile is kept."""
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=record_id).first()
            if record:
                pdf_path_str = record.pdf_path
                if pdf_path_str:
                    try:
                        pdf_path = Path(pdf_path_str)
                        if pdf_path.exists():
                            pdf_path.unlink()
                            logger.info("Successfully deleted PDF file from disk: %s", pdf_path_str)
                        else:
                            logger.warning("PDF file was already missing from disk: %s", pdf_path_str)
                    except Exception as fe:
                        logger.warning("Could not delete PDF file at %s: %s", pdf_path_str, fe)
                
                session.delete(record)
                session.commit()
                logger.info("Successfully deleted database record for payroll run ID %d", record_id)
        except Exception as e:
            session.rollback()
            logger.exception("Failed to delete payroll record ID %d", record_id)
            raise e
        finally:
            session.close()

    @staticmethod
    def get_distinct_months() -> list[str]:
        """Return distinct months found in payroll records, sorted chronologically descending."""
        session = get_session()
        try:
            results = session.query(PayrollRecord.month_year).distinct().all()
            months = [r[0] for r in results]
            
            def parse_date(my):
                try:
                    return datetime.strptime(my, "%B %Y")
                except ValueError:
                    return datetime.min
            
            return sorted(months, key=parse_date, reverse=True)
        except Exception:
            return []
        finally:
            session.close()

    @staticmethod
    def get_dashboard_stats(month_year: str) -> dict:
        """Fetch dashboard card counts and statuses filtered by selected month_year."""
        session = get_session()
        try:
            # Total permanent employees (not deleted)
            total_employees = session.query(Employee).filter_by(is_deleted=False).count()
            
            # Select month records
            month_query = session.query(PayrollRecord).filter_by(month_year=month_year)
            
            total_records = month_query.count()
            pdfs_generated = month_query.filter_by(pdf_generated=True).count()
            pdfs_pending = month_query.filter_by(pdf_generated=False).count()
            
            texts_sent = month_query.filter_by(text_status="Success").count()
            pdfs_sent = month_query.filter_by(pdf_status="Success").count()
            
            # Failed counts (either text failed or pdf failed)
            failed_messages = (
                month_query.filter(
                    (PayrollRecord.text_status == "Failed") | 
                    (PayrollRecord.pdf_status == "Failed")
                ).count()
            )
            
            # Retry queue (anything failed, or pending with at least 1 attempt)
            retry_queue = (
                month_query.filter(
                    ((PayrollRecord.text_status == "Failed") | (PayrollRecord.pdf_status == "Failed")) |
                    (((PayrollRecord.text_status == "Pending") & (PayrollRecord.text_attempts > 0)) |
                     ((PayrollRecord.pdf_status == "Pending") & (PayrollRecord.pdf_attempts > 0)))
                ).count()
            )
            
            return {
                "total_employees": total_employees,
                "total_records": total_records,
                "pdfs_generated": pdfs_generated,
                "pdfs_pending": pdfs_pending,
                "texts_sent": texts_sent,
                "pdfs_sent": pdfs_sent,
                "failed_messages": failed_messages,
                "retry_queue": retry_queue
            }
        except Exception:
            return {
                "total_employees": 0,
                "total_records": 0,
                "pdfs_generated": 0,
                "pdfs_pending": 0,
                "texts_sent": 0,
                "pdfs_sent": 0,
                "failed_messages": 0,
                "retry_queue": 0
            }
        finally:
            session.close()

    @staticmethod
    def get_recent_activity(month_year: str, limit: int = 20) -> list[dict]:
        """Fetch list of recent activities for a given month."""
        session = get_session()
        try:
            # We query payroll records for this month sorted by update time
            records = (
                session.query(PayrollRecord)
                .filter_by(month_year=month_year)
                .order_by(PayrollRecord.updated_at.desc())
                .limit(limit)
                .all()
            )
            
            activities = []
            for r in records:
                # Text Status Activity
                if r.text_attempts > 0:
                    activities.append({
                        "time": r.text_last_sent or r.updated_at,
                        "name": r.employee_name,
                        "workman_id": r.workman_id,
                        "operation": "Text Msg Send",
                        "status": r.text_status,
                        "attempts": r.text_attempts,
                        "error": r.text_error
                    })
                # PDF Status Activity
                if r.pdf_attempts > 0:
                    activities.append({
                        "time": r.pdf_last_sent or r.updated_at,
                        "name": r.employee_name,
                        "workman_id": r.workman_id,
                        "operation": "PDF Msg Send",
                        "status": r.pdf_status,
                        "attempts": r.pdf_attempts,
                        "error": r.pdf_error
                    })
                # PDF Gen Activity
                if r.pdf_generated:
                    activities.append({
                        "time": r.pdf_generated_at or r.updated_at,
                        "name": r.employee_name,
                        "workman_id": r.workman_id,
                        "operation": "PDF Generate",
                        "status": "Success",
                        "attempts": 1,
                        "error": ""
                    })
                    
            # Sort all combined activities by time desc
            activities.sort(key=lambda x: x["time"] if x["time"] else datetime.min, reverse=True)
            return activities[:limit]
        except Exception:
            return []
        finally:
            session.close()

