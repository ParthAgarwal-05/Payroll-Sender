"""SQLAlchemy database connection setup for SQLite."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from utils.logger_config import get_data_dir

# Base class for declarative ORM models
Base = declarative_base()

# Global database engine and session maker instances
_engine = None
_SessionLocal = None


def get_db_path() -> Path:
    """Return the absolute path to the SQLite database file."""
    data_dir = get_data_dir()
    db_dir = data_dir / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "payroll.db"


def init_database() -> None:
    """Initialize the SQLite engine and create tables if they do not exist."""
    global _engine, _SessionLocal
    db_path = get_db_path()
    
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
    """Check and dynamically add missing database columns to existing schemas."""
    # Check if payroll_records table exists
    cursor = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='payroll_records'")
    if cursor.fetchone():
        cursor = connection.exec_driver_sql("PRAGMA table_info(payroll_records)")
        columns = [row[1] for row in cursor.fetchall()]
        if columns and "pdf_media_id" not in columns:
            connection.exec_driver_sql("ALTER TABLE payroll_records ADD COLUMN pdf_media_id VARCHAR")


def get_session():
    """Return a new SQLAlchemy Session instance."""
    global _SessionLocal
    if _SessionLocal is None:
        init_database()
    return _SessionLocal()
