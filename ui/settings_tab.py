"""Settings page for credentials, templates, and rate limiters configuration."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QScrollArea, QGroupBox, QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox
)
from settings.settings_manager import SettingsManager
from services.whatsapp_service import WhatsAppService


class SettingsTab(QWidget):
    """Configuration form containing API key, template names, rate-limiting, and test settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        title_lbl = QLabel("Settings")
        title_lbl.setObjectName("headerTitle")
        desc_lbl = QLabel("Manage Meta WhatsApp API credentials, folders, template parameters, and retry queues.")
        desc_lbl.setObjectName("headerDesc")
        main_layout.addWidget(title_lbl)
        main_layout.addWidget(desc_lbl)

        # Scroll Area for clean desktop form scrolling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        form_layout = QVBoxLayout(scroll_content)
        form_layout.setSpacing(20)

        # --- Group 1: WhatsApp Credentials ---
        cred_group = QGroupBox("WhatsApp Credentials")
        cred_form = QFormLayout(cred_group)
        cred_form.setSpacing(10)
        
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setToolTip("Meta Cloud API Permanent Access Token")
        cred_form.addRow("Access Token:", self.token_input)

        self.phone_id_input = QLineEdit()
        cred_form.addRow("Phone Number ID:", self.phone_id_input)

        self.biz_id_input = QLineEdit()
        cred_form.addRow("Business Account ID:", self.biz_id_input)

        self.webhook_token_input = QLineEdit()
        cred_form.addRow("Verify Token (Webhook):", self.webhook_token_input)

        self.api_version_input = QLineEdit()
        cred_form.addRow("Graph API Version:", self.api_version_input)
        form_layout.addWidget(cred_group)

        # --- Group 2: Templates & PDF Delivery ---
        template_group = QGroupBox("Templates & PDF Delivery")
        template_form = QFormLayout(template_group)
        
        self.temp_name_input = QLineEdit()
        template_form.addRow("Text Template Name:", self.temp_name_input)

        self.temp_lang_input = QLineEdit()
        template_form.addRow("Template Language:", self.temp_lang_input)

        self.pdf_caption_input = QLineEdit()
        template_form.addRow("PDF Delivery Caption:", self.pdf_caption_input)

        self.pdf_dir_input = QLineEdit()
        template_form.addRow("PDF Output Folder:", self.pdf_dir_input)
        form_layout.addWidget(template_group)

        # --- Group 3: Rate Limiting & Retry ---
        rate_group = QGroupBox("Rate Limiting & Retry Settings")
        rate_form = QFormLayout(rate_group)
        
        self.mps_input = QDoubleSpinBox()
        self.mps_input.setRange(0.01, 100.0)
        self.mps_input.setSingleStep(0.1)
        rate_form.addRow("Messages Per Second (MPS):", self.mps_input)

        self.retry_count_input = QSpinBox()
        self.retry_count_input.setRange(0, 10)
        rate_form.addRow("Max Retry Count:", self.retry_count_input)

        self.retry_delay_input = QDoubleSpinBox()
        self.retry_delay_input.setRange(0.5, 60.0)
        rate_form.addRow("Base Retry Delay (sec):", self.retry_delay_input)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        rate_form.addRow("API Request Timeout (sec):", self.timeout_input)
        form_layout.addWidget(rate_group)

        # --- Group 4: Appearance & General ---
        app_group = QGroupBox("Appearance & General")
        app_form = QFormLayout(app_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light (Default Theme Override)"])
        app_form.addRow("Theme Selector:", self.theme_combo)
        form_layout.addWidget(app_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Action Buttons Row
        btn_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        btn_layout.addWidget(self.test_btn)
        
        btn_layout.addStretch()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(btn_layout)

        # Initial Load
        self.load_settings()

        # Enable text selection on all QLabels (Task 1)
        from utils.copy_helpers import enable_selection_recursive
        enable_selection_recursive(self)

    def load_settings(self):
        """Read settings values from SQLite table and populate the form fields."""
        settings = SettingsManager.get_all()
        
        self.token_input.setText(settings.get("ACCESS_TOKEN", ""))
        self.phone_id_input.setText(settings.get("PHONE_NUMBER_ID", ""))
        self.biz_id_input.setText(settings.get("BUSINESS_ACCOUNT_ID", ""))
        self.webhook_token_input.setText(settings.get("WEBHOOK_VERIFY_TOKEN", ""))
        self.api_version_input.setText(settings.get("API_VERSION", "v25.0"))
        
        self.temp_name_input.setText(settings.get("TEMPLATE_NAME", ""))
        self.temp_lang_input.setText(settings.get("TEMPLATE_LANGUAGE", ""))
        self.pdf_caption_input.setText(settings.get("PDF_CAPTION", ""))
        self.pdf_dir_input.setText(settings.get("PDF_OUTPUT_DIR", "GeneratedPdfs"))

        # Floats and Ints
        try:
            self.mps_input.setValue(float(settings.get("RATE_LIMIT_MPS", "1.0")))
            self.retry_count_input.setValue(int(settings.get("RETRY_COUNT", "3")))
            self.retry_delay_input.setValue(float(settings.get("RETRY_DELAY", "2.0")))
            self.timeout_input.setValue(int(settings.get("TIMEOUT_SECONDS", "30")))
        except ValueError:
            pass

        theme = settings.get("THEME", "Dark")
        if theme == "Dark":
            self.theme_combo.setCurrentIndex(0)
        else:
            self.theme_combo.setCurrentIndex(1)

    def save_settings(self, silent=False):
        """Harvest input fields and save settings to SQLite table."""
        settings_dict = {
            "ACCESS_TOKEN": self.token_input.text().strip(),
            "PHONE_NUMBER_ID": self.phone_id_input.text().strip(),
            "BUSINESS_ACCOUNT_ID": self.biz_id_input.text().strip(),
            "WEBHOOK_VERIFY_TOKEN": self.webhook_token_input.text().strip(),
            "API_VERSION": self.api_version_input.text().strip(),
            
            "TEMPLATE_NAME": self.temp_name_input.text().strip(),
            "TEMPLATE_LANGUAGE": self.temp_lang_input.text().strip(),
            "PDF_CAPTION": self.pdf_caption_input.text().strip(),
            "PDF_OUTPUT_DIR": self.pdf_dir_input.text().strip(),
            
            "RATE_LIMIT_MPS": str(self.mps_input.value()),
            "RETRY_COUNT": str(self.retry_count_input.value()),
            "RETRY_DELAY": str(self.retry_delay_input.value()),
            "TIMEOUT_SECONDS": str(self.timeout_input.value()),
            
            "THEME": "Dark" if self.theme_combo.currentIndex() == 0 else "Light",
        }

        try:
            SettingsManager.save_settings(settings_dict)
            if not silent:
                QMessageBox.information(self, "Settings Saved", "Application configuration saved successfully.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not write settings to database:\n{str(e)}")
            return False

    def test_connection(self):
        """Save settings first, then test Meta Graph credentials by validating Phone ID."""
        if not self.save_settings(silent=True):
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        
        # Run test inside the main thread (validate_credentials has a 20s timeout, but usually completes in 1-2s)
        try:
            # Re-read settings loaded into env inside save_settings
            client = WhatsAppService()
            success, msg = client.validate_credentials()
            
            if success:
                QMessageBox.information(self, "Connection Verified", "Success! Connection to Meta API is verified and active.")
            else:
                QMessageBox.warning(self, "Connection Failed", f"Credentials rejected by Meta Graph API:\n{msg}")
        except Exception as e:
            QMessageBox.critical(self, "Test Failed", f"An exception occurred during testing:\n{str(e)}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")
