"""SQLAlchemy models for Employees, Payroll Records, and Settings."""

import uuid
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship
from database.db import Base


class Employee(Base):
    """Permanent employee record."""
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_uuid = Column(String, unique=True, index=True, nullable=False, default=lambda: uuid.uuid4().hex)
    workman_id = Column(String, index=True, nullable=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    designation = Column(String, nullable=True)
    uan = Column(String, nullable=True)
    bank_account = Column(String, nullable=True)
    guardian_name = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to payroll records
    payroll_records = relationship("PayrollRecord", back_populates="employee", cascade="all, delete-orphan")


class PayrollRecord(Base):
    """Monthly payroll details, PDF metadata, and WhatsApp statuses for one employee."""
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "month", "year", name="uq_employee_month_year"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    workman_id = Column(String, nullable=True)
    
    # Period details
    month = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month_year = Column(String, index=True, nullable=False)  # "January 2026"
    
    # Professional details
    establishment = Column(String, nullable=True)
    principal_employer = Column(String, nullable=True)
    address = Column(String, nullable=True)
    employee_name = Column(String, nullable=False)
    guardian_name = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    uan = Column(String, nullable=True)
    bank_account = Column(String, nullable=True)
    wage_period = Column(String, nullable=True)
    
    # Wages details
    attendance = Column(Float, default=0.0)
    basic = Column(Float, default=0.0)
    da = Column(Float, default=0.0)
    allowances = Column(Float, default=0.0)
    gross_wages = Column(Float, default=0.0)
    pf = Column(Float, default=0.0)
    esi = Column(Float, default=0.0)
    other_deductions = Column(Float, default=0.0)
    net_wages = Column(Float, default=0.0)
    issue_date = Column(String, nullable=True)
    
    # PDF generation details
    pdf_path = Column(String, nullable=True)
    pdf_generated = Column(Boolean, default=False, nullable=False)
    pdf_generated_at = Column(DateTime, nullable=True)
    pdf_uuid = Column(String, nullable=True)
    
    # WhatsApp Text sending status
    text_status = Column(String, default="Pending", nullable=False)  # "Pending", "Success", "Failed"
    text_message_id = Column(String, nullable=True)
    text_attempts = Column(Integer, default=0, nullable=False)
    text_last_sent = Column(DateTime, nullable=True)
    text_error = Column(String, nullable=True)
    
    # WhatsApp PDF sending status
    pdf_status = Column(String, default="Pending", nullable=False)  # "Pending", "Success", "Failed"
    pdf_message_id = Column(String, nullable=True)
    pdf_media_id = Column(String, nullable=True)
    pdf_attempts = Column(Integer, default=0, nullable=False)
    pdf_last_sent = Column(DateTime, nullable=True)
    pdf_error = Column(String, nullable=True)
    
    # Metadata timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to employee profile
    employee = relationship("Employee", back_populates="payroll_records")


class Setting(Base):
    """Key-value settings storage table."""
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True, nullable=False)
    value = Column(String, nullable=True)
