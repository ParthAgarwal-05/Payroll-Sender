"""PDF Generation service for official government-style wage slips."""

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from database.db import get_session
from database.models import PayrollRecord, Employee
from settings.settings_manager import SettingsManager


def format_val(val: Any) -> str:
    """Format numeric values cleanly as integer strings if whole, otherwise float."""
    if val is None:
        return ""
    try:
        f_val = float(val)
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.2f}"
    except (ValueError, TypeError):
        return str(val)


def generate_wage_slip(payroll: Any, company_info: dict[str, str]) -> bytes:
    """Generate an official government-style bordered PDF wage slip (Form VIII-C, Rule 156)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    # Styles
    styles = getSampleStyleSheet()
    
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.black,
    )
    value_style = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.black,
    )
    header_bold = ParagraphStyle(
        "HeaderBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        textColor=colors.black,
    )
    header_normal = ParagraphStyle(
        "HeaderNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=1,  # Center
        textColor=colors.black,
    )
    header_small = ParagraphStyle(
        "HeaderSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=1,  # Center
        textColor=colors.black,
    )

    # Fetch values directly from the stored DB record
    issue_date = getattr(payroll, "issue_date", "") or ""
    establishment = getattr(payroll, "establishment", "") or ""
    principal_employer = getattr(payroll, "principal_employer", "") or ""
    address = getattr(payroll, "address", "") or ""
    
    emp_name = getattr(payroll, "employee_name", "") or ""
    guardian_name = getattr(payroll, "guardian_name", "") or ""
    designation = getattr(payroll, "designation", "") or ""
    uan = getattr(payroll, "uan", "") or ""
    bank_account = getattr(payroll, "bank_account", "") or ""
    wage_period = getattr(payroll, "wage_period", "") or ""
    workman_id = getattr(payroll, "workman_id", "") or ""

    # Rate of wages payable
    basic_str = format_val(getattr(payroll, "basic", None))
    da_str = format_val(getattr(payroll, "da", None))
    allowances_str = format_val(getattr(payroll, "allowances", None))
    
    # Attendance, Overtime, Gross, Deductions, Net
    attendance_str = format_val(getattr(payroll, "attendance", None))
    overtime_str = "0"
    gross_wages_str = format_val(getattr(payroll, "gross_wages", None))
    pf_str = format_val(getattr(payroll, "pf", None))
    esi_str = format_val(getattr(payroll, "esi", None))
    other_ded_str = format_val(getattr(payroll, "other_deductions", None))
    net_wages_str = format_val(getattr(payroll, "net_wages", None))

    # Grid data array
    table_data = [
        # 0-2: Header section
        [Paragraph("WAGE SLIP", header_bold), "", "", "", ""],
        [Paragraph("FORM — VIII-C", header_normal), "", "", "", ""],
        [Paragraph("(See rule 156)", header_small), "", "", "", ""],
        
        # 3: Date of issue
        [Paragraph(f"Date of issue: {issue_date}", label_style), "", "", "", ""],
        
        # 4: Name of Establishment
        [Paragraph(f"Name of Establishment : {establishment}", label_style), "", "", "", ""],
        
        # 5: Name of Principal Employer
        [Paragraph(f"Name of Principal Employer : {principal_employer}", label_style), "", "", "", ""],
        
        # 6: Address / Period
        [
            Paragraph(f"Address: {address}", label_style),
            "",
            Paragraph("Period:", label_style),
            Paragraph(wage_period, value_style),
            ""
        ],
        
        # 7: Name of Employee
        [Paragraph("1.", label_style), Paragraph("Name of the Employee:", label_style), Paragraph(emp_name, value_style), "", ""],
        
        # 8: Father's/Mother's/Spouse's Name
        [Paragraph("2.", label_style), Paragraph("Father's/Mother's/Spouse's Name:", label_style), Paragraph(guardian_name, value_style), "", ""],
        
        # 9: Designation
        [Paragraph("3.", label_style), Paragraph("Designation:", label_style), Paragraph(designation, value_style), "", ""],
        
        # 10: UAN
        [Paragraph("4.", label_style), Paragraph("UAN:", label_style), Paragraph(uan, value_style), "", ""],
        
        # 11: Bank Account Number
        [Paragraph("5.", label_style), Paragraph("Bank Account Number:", label_style), Paragraph(bank_account, value_style), "", ""],
        
        # 12: Wage period details
        [Paragraph("6.", label_style), Paragraph("Wage period:", label_style), Paragraph(wage_period, value_style), "", ""],
        
        # 13: Rate of wages payable labels
        [
            Paragraph("7.", label_style),
            Paragraph("Rate of wages payable", label_style),
            Paragraph("a) Basic", label_style),
            Paragraph("b) D.A.", label_style),
            Paragraph("c) other allowances", label_style)
        ],
        
        # 14: Rate of wages payable values
        [
            "",
            "",
            Paragraph(basic_str, value_style),
            Paragraph(da_str, value_style),
            Paragraph(allowances_str, value_style)
        ],
        
        # 15: Attendance
        [Paragraph("8.", label_style), Paragraph("Total attendance/unit of work done:", label_style), Paragraph(attendance_str, value_style), "", ""],
        
        # 16: Overtime wages
        [Paragraph("9.", label_style), Paragraph("Overtime wages:", label_style), Paragraph(overtime_str, value_style), "", ""],
        
        # 17: Gross wages payable
        [Paragraph("10.", label_style), Paragraph("Gross wages payable:", label_style), Paragraph(gross_wages_str, value_style), "", ""],
        
        # 18: Total deductions labels
        [
            Paragraph("11.", label_style),
            Paragraph("Total deductions", label_style),
            Paragraph("a) PF", label_style),
            Paragraph("b) ESI", label_style),
            Paragraph("c) Others", label_style)
        ],
        
        # 19: Total deductions values
        [
            "",
            "",
            Paragraph(pf_str, value_style),
            Paragraph(esi_str, value_style),
            Paragraph(other_ded_str, value_style)
        ],
        
        # 20: Net wages paid
        [Paragraph("12.", label_style), Paragraph("Net wages paid:", label_style), Paragraph(net_wages_str, value_style), "", ""]
    ]

    col_widths = [25, 175, 110, 110, 112]
    table = Table(table_data, colWidths=col_widths)
    
    table.setStyle(
        TableStyle([
            ("SPAN", (0, 0), (4, 0)),  # WAGE SLIP
            ("SPAN", (0, 1), (4, 1)),  # FORM — VIII-C
            ("SPAN", (0, 2), (4, 2)),  # (See rule 156)
            ("SPAN", (0, 3), (4, 3)),  # Date of issue
            ("SPAN", (0, 4), (4, 4)),  # Name of Establishment
            ("SPAN", (0, 5), (4, 5)),  # Principal Employer
            ("SPAN", (0, 6), (1, 6)),  # Address
            ("SPAN", (3, 6), (4, 6)),  # Period value
            
            ("SPAN", (2, 7), (4, 7)),   # Employee Name
            ("SPAN", (2, 8), (4, 8)),   # Guardian Name
            ("SPAN", (2, 9), (4, 9)),   # Designation
            ("SPAN", (2, 10), (4, 10)), # UAN
            ("SPAN", (2, 11), (4, 11)), # Bank Account
            ("SPAN", (2, 12), (4, 12)), # Wage period
            
            ("SPAN", (0, 13), (0, 14)), # 7.
            ("SPAN", (1, 13), (1, 14)), # Rate of wages payable label
            
            ("SPAN", (2, 15), (4, 15)), # Attendance
            ("SPAN", (2, 16), (4, 16)), # Overtime
            ("SPAN", (2, 17), (4, 17)), # Gross wages
            
            ("SPAN", (0, 18), (0, 19)), # 11.
            ("SPAN", (1, 18), (1, 19)), # Total deductions label
            
            ("SPAN", (2, 20), (4, 20)), # Net wages
            
            ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )

    story.append(table)
    
    # Modest white space after table
    story.append(Spacer(1, 15))
    
    # Create the signature table right-aligned
    signature_style = ParagraphStyle(
        "SignatureStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=1,  # Center text relative to its column
        textColor=colors.black,
    )
    sig_data = [
        [""],
        [Paragraph("Employer / Pay-in-charge", signature_style)],
        [Paragraph("Signature", signature_style)]
    ]
    sig_table = Table(sig_data, colWidths=[200], rowHeights=[40, 18, 18], hAlign='RIGHT')
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(sig_table)
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


class PdfService:
    """Manages generation of PDFs and organized file system storage."""

    @staticmethod
    def generate_and_save(payroll_record_id: int) -> str:
        """Load a payroll record, render PDF, save it organized by Month/Year, and update DB.

        Path format: GeneratedPdfs/<Year>/<Month>/<pdf_uuid>.pdf
        """
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=payroll_record_id).first()
            if not record:
                raise ValueError(f"Payroll record {payroll_record_id} not found.")

            # Load Company Details from settings if needed
            company_info = {
                "name": record.establishment or "Establishment Name",
                "address": record.address or "Address",
            }

            # Retrieve folder path from settings
            base_dir_setting = SettingsManager.get("PDF_OUTPUT_DIR", "GeneratedPdfs")
            base_dir = Path(base_dir_setting)
            
            # Format subfolders: Year / Month
            month_folder = record.month.strip().capitalize()
            year_folder = str(record.year)
            
            target_dir = base_dir / year_folder / month_folder
            target_dir.mkdir(parents=True, exist_ok=True)

            # Ensure pdf_uuid is generated defensively checking for collisions on disk
            if not record.pdf_uuid:
                import uuid
                while True:
                    candidate_uuid = uuid.uuid4().hex
                    candidate_filename = f"{candidate_uuid}.pdf"
                    candidate_path = target_dir / candidate_filename
                    if not candidate_path.exists():
                        record.pdf_uuid = candidate_uuid
                        break

            # Generate binary PDF bytes
            pdf_bytes = generate_wage_slip(record, company_info)
            
            filename = f"{record.pdf_uuid}.pdf"
            file_path = target_dir / filename
            
            # Write to disk
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)

            # Update payroll record in DB
            record.pdf_path = str(file_path.resolve())
            record.pdf_generated = True
            record.pdf_generated_at = datetime.now()
            record.pdf_media_id = None
            session.commit()

            return record.pdf_path

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
