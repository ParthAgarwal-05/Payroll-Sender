"""Database backup and restore utilities for SQLite."""

import sqlite3
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger("DatabaseBackup")


def verify_integrity(db_path: Path) -> bool:
    """Perform PRAGMA integrity_check on the database to verify it is not corrupted."""
    if not db_path.exists():
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            return True
        logger.error("Database integrity check failed for %s: %s", db_path, result)
        return False
    except Exception as e:
        logger.exception("Database integrity verification failed for %s: %s", db_path, e)
        return False
    finally:
        if conn:
            conn.close()


def sqlite_backup(source_path: Path, target_path: Path) -> None:
    """Safe WAL-aware backup using sqlite3 backup API."""
    src = None
    dst = None
    try:
        src = sqlite3.connect(str(source_path))
        dst = sqlite3.connect(str(target_path))
        src.backup(dst)
        dst.commit()
    finally:
        if src:
            src.close()
        if dst:
            dst.close()


def create_backup(db_path: Path, backup_dir: Path, prefix: str = "auto") -> Path:
    """Create a verified, timestamped backup of the database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{prefix}_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    logger.info("Starting database backup to: %s", backup_path)
    sqlite_backup(db_path, backup_path)

    # Verify backup integrity
    if not verify_integrity(backup_path):
        # Integrity failed, clean up the corrupted backup file
        if backup_path.exists():
            backup_path.unlink()
        raise RuntimeError("Created database backup failed integrity check. Verification aborted.")

    logger.info("Database backup created and verified successfully: %s", backup_path)
    return backup_path


def restore_db(backup_path: Path, db_path: Path) -> None:
    """Safely restore database from backup, ensuring engine disposal and clean journal unlinking."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Verify the integrity of the backup before restoring it!
    if not verify_integrity(backup_path):
        raise ValueError("Cannot restore backup: The backup database file is corrupted.")

    # Dispose the active SQLAlchemy engine if it exists
    from database.db import dispose_engine
    dispose_engine()
    import gc
    gc.collect()

    # Clean up journal files to prevent corruption when starting with the new database
    wal_path = db_path.with_name(db_path.name + "-wal")
    shm_path = db_path.with_name(db_path.name + "-shm")

    if wal_path.exists():
        try:
            wal_path.unlink()
        except Exception:
            pass
    if shm_path.exists():
        try:
            shm_path.unlink()
        except Exception:
            pass

    # Perform atomic restore
    temp_target = db_path.with_name(f".{db_path.name}.restore_tmp")
    try:
        sqlite_backup(backup_path, temp_target)
        try:
            temp_target.replace(db_path)
        except PermissionError:
            # Fallback for Windows file locks: copy directly via sqlite backup API
            sqlite_backup(backup_path, db_path)
            if temp_target.exists():
                try:
                    temp_target.unlink()
                except Exception:
                    pass
    except Exception as e:
        if temp_target.exists():
            try:
                temp_target.unlink()
            except Exception:
                pass
        raise e

    logger.info("Database restored successfully from: %s", backup_path)
