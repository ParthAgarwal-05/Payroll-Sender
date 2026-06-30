"""Logging configuration module for the Payroll Management System.

Provides a centralized logger setup with rotating file output and console
streaming, ensuring consistent log formatting across all modules.
Includes PII privacy filtering to mask salaries, phone numbers, and accounts.
"""

import logging
import os
import platform
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_app_dir() -> Path:
    """Return the directory containing bundled application assets."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """Return the directory for user-writable application data.

    In production (frozen mode), data is stored in the platform-appropriate
    user data directory. In development, it defaults to the project root.
    """
    override = os.environ.get('PAYROLL_DATA_DIR')
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p

    if getattr(sys, 'frozen', False):
        if platform.system() == 'Windows':
            base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        else:
            base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        data_dir = base / 'DesktopPayrollSystem'
    else:
        # Development: use project root directory
        data_dir = Path(__file__).resolve().parent.parent

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def mask_pii(text: str) -> str:
    """Mask personally identifiable information in log text.

    Masks:
    - Phone numbers (sequences of 10+ digits)
    - Values that look like account numbers
    - Common sensitive fields
    """
    if not text:
        return text
    # Mask phone-like sequences (10+ digits)
    text = re.sub(r'\+?\d{10,}', lambda m: m.group()[:3] + '****' + m.group()[-3:], text)
    # Mask values after sensitive keywords
    for keyword in ('bank_account', 'uan', 'account', 'net_wages', 'basic',
                    'gross_wages', 'da', 'allowances', 'pf', 'esi', 'salary', 'other_deductions'):
        # JSON format
        text = re.sub(
            rf'("{keyword}"\s*:\s*")([^"]+)(")',
            rf'\1***MASKED***\3',
            text,
            flags=re.IGNORECASE,
        )
        # Template parameter format
        text = re.sub(
            rf'("parameter_name"\s*:\s*"{keyword}"\s*,\s*"text"\s*:\s*")([^"]+)(")',
            rf'\1***MASKED***\3',
            text,
            flags=re.IGNORECASE,
        )
    return text


class PrivacyFilter(logging.Filter):
    """Logging filter that masks PII in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_pii(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_pii(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def setup_logger(name: str = 'PayrollSystem') -> logging.Logger:
    """Create and configure a logger with file and console handlers."""
    data_dir: Path = get_data_dir()
    log_dir: Path = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file: Path = log_dir / "payroll_system.log"

    logger: logging.Logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    privacy_filter = PrivacyFilter()
    formatter: logging.Formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler
    file_handler: RotatingFileHandler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(privacy_filter)

    # Console handler
    console_handler: logging.StreamHandler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(privacy_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
