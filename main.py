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
        # Launch PySide6 GUI QApplication first to allow early GUI error notifications
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # 2. Setup SQLite Database and SQLAlchemy tables
        init_database()
        logger.info("SQLite database schema initialized successfully.")

        # 3. Reload settings from DB table to environment variables
        SettingsManager.load_to_env()
        logger.info("Application configuration reloaded from settings table.")
        
        window = MainWindow()
        window.show()
        
        logger.info("Application GUI rendered. Entering event loop...")
        sys.exit(app.exec())

    except Exception as e:
        logger.critical("Fatal crash during startup: %s", e, exc_info=True)
        if QApplication.instance():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, "Fatal Startup Error",
                f"The application encountered a fatal error during startup:\n\n{str(e)}\n\nPlease restore the database from a backup or contact support."
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
