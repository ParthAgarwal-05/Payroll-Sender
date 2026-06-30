"""Manager for database-backed application settings."""

import os
from database.db import get_session
from database.models import Setting

DEFAULT_SETTINGS = {
    # WhatsApp Credentials
    "ACCESS_TOKEN": "",
    "PHONE_NUMBER_ID": "",
    "BUSINESS_ACCOUNT_ID": "",
    "WEBHOOK_VERIFY_TOKEN": "",
    "API_VERSION": "v25.0",
    
    # Templates
    "TEMPLATE_NAME": "wageslip",
    "PDF_TEMPLATE_NAME": "wageslip_pdf",
    "TEMPLATE_LANGUAGE": "en",
    
    # PDF Settings
    "PDF_CAPTION": "Please find attached your wage slip for this month.",
    "PDF_OUTPUT_DIR": "GeneratedPdfs",
    
    # Rate Limiting & Retry
    "RATE_LIMIT_MPS": "1.0",
    "RETRY_COUNT": "3",
    "RETRY_DELAY": "2.0",
    "TIMEOUT_SECONDS": "30",
    
    # UI Theme
    "THEME": "Dark",
}


class SettingsManager:
    """Handles persistent application configuration stored in SQLite database."""

    @staticmethod
    def get(key: str, default: str = "") -> str:
        """Retrieve a setting by key. Fall back to defaults if not found in database."""
        session = get_session()
        try:
            setting = session.query(Setting).filter_by(key=key).first()
            if setting is not None:
                return setting.value
            return DEFAULT_SETTINGS.get(key, default)
        except Exception:
            return DEFAULT_SETTINGS.get(key, default)
        finally:
            session.close()

    @staticmethod
    def get_all() -> dict[str, str]:
        """Retrieve all settings. Populate defaults for missing keys."""
        session = get_session()
        try:
            settings = {s.key: s.value for s in session.query(Setting).all()}
            for k, v in DEFAULT_SETTINGS.items():
                if k not in settings:
                    settings[k] = v
            return settings
        except Exception:
            return DEFAULT_SETTINGS.copy()
        finally:
            session.close()

    @staticmethod
    def set(key: str, value: str) -> None:
        """Set a setting key to a value and persist it in the database."""
        session = get_session()
        try:
            setting = session.query(Setting).filter_by(key=key).first()
            if setting is not None:
                setting.value = str(value)
            else:
                setting = Setting(key=key, value=str(value))
                session.add(setting)
            session.commit()
            
            # Synchronize with environment variables for components reading from os.getenv
            os.environ[key] = str(value)
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def save_settings(settings_dict: dict[str, str]) -> None:
        """Save a dictionary of settings keys and values."""
        session = get_session()
        try:
            for k, v in settings_dict.items():
                setting = session.query(Setting).filter_by(key=k).first()
                if setting is not None:
                    setting.value = str(v)
                else:
                    setting = Setting(key=k, value=str(v))
                    session.add(setting)
                # Sync environment variables
                os.environ[k] = str(v)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @classmethod
    def load_to_env(cls) -> None:
        """Load all settings from the database into OS environment variables.

        Ensures that modules reading from os.getenv (like legacy modules)
        have immediate access to current database settings.
        """
        all_settings = cls.get_all()
        for k, v in all_settings.items():
            os.environ[k] = str(v)
