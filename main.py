"""Main entry point to execute the PySide6 Payroll & WhatsApp Management System."""

import sys
from PySide6.QtWidgets import QApplication
from database.db import init_database
from settings.settings_manager import SettingsManager
from ui.main_window import MainWindow
from utils.logger_config import setup_logger


def main():
    # 1. Setup centralized logs
    logger = setup_logger("Main")
    logger.info("Starting Payroll Manager Desktop Application...")

    try:
        # 2. Setup SQLite Database and SQLAlchemy tables
        init_database()
        logger.info("SQLite database schema initialized successfully.")

        # 3. Reload settings from DB table to environment variables
        SettingsManager.load_to_env()
        logger.info("Application configuration reloaded from settings table.")

        # 4. Launch PySide6 GUI QApplication
        app = QApplication(sys.argv)
        
        # We can set an application-wide stylesheet / styling configurations if needed
        app.setStyle("Fusion")
        
        window = MainWindow()
        window.show()
        
        logger.info("Application GUI rendered. Entering event loop...")
        sys.exit(app.exec())

    except Exception as e:
        logger.critical("Fatal crash during startup: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
