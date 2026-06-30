"""SQLAlchemy database connection setup for SQLite."""

import uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from utils.logger_config import get_data_dir, setup_logger

# Base class for declarative ORM models
Base = declarative_base()

# Global database engine and session maker instances
_engine = None
_SessionLocal = None

logger = setup_logger("DatabaseInit")


def get_db_path() -> Path:
    """Return the absolute path to the SQLite database file."""
    data_dir = get_data_dir()
    db_dir = data_dir / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "payroll.db"


def dispose_engine() -> None:
    """Dispose the global engine and clear session maker (required for DB restore)."""
    global _engine, _SessionLocal
    if _engine:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
    _SessionLocal = None


def init_database() -> None:
    """Initialize the SQLite engine and create tables if they do not exist."""
    global _engine, _SessionLocal
    
    # Force load models to ensure table registration on Base.metadata
    import database.models
    
    db_path = get_db_path()
    
    # Run SQLite integrity check on startup
    if db_path.exists():
        from database.backup import verify_integrity
        if not verify_integrity(db_path):
            logger.critical("Database integrity check failed! The database file is corrupted.")
            raise RuntimeError("Database integrity verification failed: The database file is corrupted.")

    # Create backup before running migrations
    if db_path.exists():
        try:
            from database.backup import create_backup
            backup_dir = db_path.parent / "backups"
            create_backup(db_path, backup_dir, prefix="pre_migration")
            logger.info("Pre-migration backup completed successfully.")
        except Exception as e:
            logger.error("Could not complete automatic pre-migration database backup: %s", e)
            
    # Create SQLAlchemy engine for SQLite with thread-safety parameters
    # check_same_thread=False is safe because we serialise writes or use sessions appropriately
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    
    # Configure WAL mode for concurrent reading/writing and set busy timeout
    with _engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA busy_timeout=5000")
        
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    
    # Create all tables defined in models
    Base.metadata.create_all(bind=_engine)
    
    # Run sqlite migrations
    with _engine.begin() as connection:
        run_migrations(connection)


def run_migrations(connection) -> None:
    """Check and dynamically add missing database columns or recreate tables to update constraints/relationships."""
    # Check if employees table exists
    cursor = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
    has_employees = cursor.fetchone() is not None
    
    cursor = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='payroll_records'")
    has_payroll = cursor.fetchone() is not None
    
    needs_migration = False
    
    existing_employees = []
    emp_cols = []
    if has_employees:
        cursor = connection.exec_driver_sql("PRAGMA table_info(employees)")
        emp_cols = [row[1] for row in cursor.fetchall()]
        if "employee_uuid" not in emp_cols:
            needs_migration = True
            
        cursor = connection.exec_driver_sql("SELECT * FROM employees")
        for row in cursor.fetchall():
            emp_dict = dict(zip(emp_cols, row))
            if not emp_dict.get("employee_uuid"):
                emp_dict["employee_uuid"] = uuid.uuid4().hex
            existing_employees.append(emp_dict)
            
    existing_payroll = []
    pr_cols = []
    if has_payroll:
        cursor = connection.exec_driver_sql("PRAGMA table_info(payroll_records)")
        pr_cols = [row[1] for row in cursor.fetchall()]
        if "employee_id" not in pr_cols:
            needs_migration = True
            
        cursor = connection.exec_driver_sql("SELECT * FROM payroll_records")
        for row in cursor.fetchall():
            existing_payroll.append(dict(zip(pr_cols, row)))

    if needs_migration:
        logger.info("Database schema upgrade required. Recreating tables and migrating existing records...")
        
        # Turn off foreign key checks temporarily
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        
        # Drop old tables
        connection.exec_driver_sql("DROP TABLE IF EXISTS payroll_records")
        connection.exec_driver_sql("DROP TABLE IF EXISTS employees")
        
        # Recreate tables with new schema bound to transactional connection
        Base.metadata.create_all(bind=connection)
        
        # Insert employees back, preserving all values and generating missing UUIDs
        from datetime import datetime
        valid_emp_keys = [c.name for c in Base.metadata.tables["employees"].columns]
        for emp in existing_employees:
            if not emp.get("created_at"):
                emp["created_at"] = datetime.now()
            if not emp.get("updated_at"):
                emp["updated_at"] = datetime.now()
            if "is_deleted" not in emp or emp["is_deleted"] is None:
                emp["is_deleted"] = 0
                
            emp_filtered = {k: v for k, v in emp.items() if k in valid_emp_keys}
            cols = list(emp_filtered.keys())
            cols_str = ", ".join([f'"{c}"' for c in cols])
            bind_str = ", ".join([f":{c}" for c in cols])
            connection.execute(
                text(f"INSERT INTO employees ({cols_str}) VALUES ({bind_str})"),
                emp_filtered
            )
            
        # Build maps to resolve employee_id for payroll_records
        id_map_by_workman = {}
        for emp in existing_employees:
            emp_id = emp["id"]
            w_id = emp.get("workman_id")
            if w_id:
                id_map_by_workman[w_id.strip().upper()] = emp_id
                
        # Insert payroll records back, resolving employee_id and preserving existing data
        valid_keys = [c.name for c in Base.metadata.tables["payroll_records"].columns]
        for pr in existing_payroll:
            emp_id = None
            w_id = pr.get("workman_id")
            if w_id:
                emp_id = id_map_by_workman.get(w_id.strip().upper())
            
            # Fallback if no matching employee exists (e.g. if profile was somehow deleted or orphan)
            if not emp_id and existing_employees:
                emp_id = existing_employees[0]["id"]
            
            if not emp_id:
                logger.warning("Orphan payroll record %s skipped due to no employees in database", pr.get("id"))
                continue
                
            pr["employee_id"] = emp_id
            
            if "pdf_generated" not in pr or pr["pdf_generated"] is None:
                pr["pdf_generated"] = 0
            if "text_status" not in pr or pr["text_status"] is None:
                pr["text_status"] = "Pending"
            if "pdf_status" not in pr or pr["pdf_status"] is None:
                pr["pdf_status"] = "Pending"
            if "text_attempts" not in pr or pr["text_attempts"] is None:
                pr["text_attempts"] = 0
            if "pdf_attempts" not in pr or pr["pdf_attempts"] is None:
                pr["pdf_attempts"] = 0
            if "created_at" not in pr or pr["created_at"] is None:
                pr["created_at"] = datetime.now()
            if "updated_at" not in pr or pr["updated_at"] is None:
                pr["updated_at"] = datetime.now()
                
            pr_filtered = {k: v for k, v in pr.items() if k in valid_keys}
            cols = list(pr_filtered.keys())
            cols_str = ", ".join([f'"{c}"' for c in cols])
            bind_str = ", ".join([f":{c}" for c in cols])
            connection.execute(
                text(f"INSERT INTO payroll_records ({cols_str}) VALUES ({bind_str})"),
                pr_filtered
            )
            
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        logger.info("Database schema migration completed successfully.")
    else:
        if has_payroll:
            cursor = connection.exec_driver_sql("PRAGMA table_info(payroll_records)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and "pdf_media_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE payroll_records ADD COLUMN pdf_media_id VARCHAR")
            if columns and "pdf_uuid" not in columns:
                connection.exec_driver_sql("ALTER TABLE payroll_records ADD COLUMN pdf_uuid VARCHAR")


def get_session():
    """Return a new SQLAlchemy Session instance."""
    global _SessionLocal
    if _SessionLocal is None:
        init_database()
    return _SessionLocal()
