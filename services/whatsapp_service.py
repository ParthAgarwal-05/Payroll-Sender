"""Service for sending WhatsApp messages (text templates and PDF document slips)."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

from database.db import get_session
from database.models import PayrollRecord
from settings.settings_manager import SettingsManager
from utils.phone_utils import normalize_phone
from utils.rate_limiter import RateLimiter
from utils.logger_config import setup_logger, mask_pii


class WhatsAppService:
    """Client for Meta WhatsApp Cloud API and Media API with built-in rate-limiting and retry logic."""

    NON_RETRIABLE_CODES: set[int] = {400, 401, 403, 404}
    RETRIABLE_CODES: set[int] = {429, 500, 502, 503, 504}

    def __init__(self) -> None:
        self.logger = setup_logger(__name__)
        
        # Load configurations from settings database
        self.access_token = SettingsManager.get("ACCESS_TOKEN", "")
        self.phone_number_id = SettingsManager.get("PHONE_NUMBER_ID", "")
        self.business_account_id = SettingsManager.get("BUSINESS_ACCOUNT_ID", "")
        self.api_version = SettingsManager.get("API_VERSION", "v25.0")
        
        self.template_name = SettingsManager.get("TEMPLATE_NAME", "wageslip")
        self.template_language = SettingsManager.get("TEMPLATE_LANGUAGE", "en")
        self.pdf_caption = SettingsManager.get("PDF_CAPTION", "")
        
        # Setup API URLs
        self.api_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        self.media_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/media"
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # Initialize rate limiter
        rate_limit_raw = SettingsManager.get("RATE_LIMIT_MPS", "1.0")
        try:
            rate_limit = float(rate_limit_raw)
            if rate_limit <= 0:
                rate_limit = 1.0
        except ValueError:
            rate_limit = 1.0
            
        self._rate_limiter = RateLimiter(max_per_second=rate_limit)

    def validate_credentials(self) -> tuple[bool, str]:
        """Verify that the configured WhatsApp API credentials are valid using a lightweight GET request."""
        if not self.access_token or not self.phone_number_id:
            return False, "Access Token and Phone Number ID are required settings."
            
        validation_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        self.logger.info("Validating credentials against %s", validation_url)
        try:
            response = requests.get(validation_url, headers=headers, timeout=20)
            self.logger.info("Validation response status: %d", response.status_code)
            
            if response.status_code == 200:
                return True, "Connection successful! Credentials are valid."
                
            try:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_message = response.text
                
            return False, f"HTTP {response.status_code}: {error_message}"
        except Exception as exc:
            self.logger.error("Credential validation failed: %s", exc)
            return False, f"Network connection failed: {str(exc)}"

    def upload_pdf_media(self, pdf_path: str) -> str:
        """Upload a PDF file using Meta Media API and return the media_id string on success."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found for upload: {pdf_path}")
            
        self.logger.info("Uploading PDF to WhatsApp Media API: %s", pdf_path)
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        filename = os.path.basename(pdf_path)
        files = {
            "file": (filename, open(pdf_path, "rb"), "application/pdf")
        }
        data = {
            "messaging_product": "whatsapp",
            "type": "document"
        }
        
        try:
            response = requests.post(
                self.media_url,
                headers=headers,
                files=files,
                data=data,
                timeout=60
            )
            
            # Close file handle
            files["file"][1].close()
            
            self.logger.info("Media upload response status: %d", response.status_code)
            
            if response.status_code in (200, 201):
                response_data = response.json()
                media_id = response_data.get("id", "")
                if media_id:
                    self.logger.info("Uploaded successfully. Media ID: %s", media_id)
                    return media_id
                raise ValueError("Response succeeded but did not contain media ID.")
                
            try:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_message = response.text
                
            raise ValueError(f"HTTP {response.status_code}: {error_message}")
            
        except Exception as exc:
            self.logger.error("Media upload exception: %s", exc)
            raise exc

    def build_template_payload(self, phone: str, record: Any) -> dict:
        """Build WhatsApp Cloud API template-message payload using consolidated fields from record."""
        TEMPLATE_FIELDS = [
            "month_year",
            "establishment",
            "principal_employer",
            "address",
            "employee_name",
            "workman_id",
            "guardian_name",
            "designation",
            "uan",
            "bank_account",
            "wage_period",
            "attendance",
            "basic",
            "da",
            "allowances",
            "gross_wages",
            "pf",
            "esi",
            "other_deductions",
            "net_wages",
            "issue_date",
        ]

        parameters = []
        for field in TEMPLATE_FIELDS:
            val = getattr(record, field, "")
            if val is None:
                val = ""
            
            # Format numeric values cleanly
            if field in ("basic", "da", "allowances", "gross_wages", "pf", "esi", "other_deductions", "net_wages"):
                try:
                    f_val = float(val)
                    if f_val.is_integer():
                        val_str = f"{int(f_val)}"
                    else:
                        val_str = f"{f_val:.2f}"
                except (ValueError, TypeError):
                    val_str = str(val)
            elif field == "attendance":
                try:
                    f_val = float(val)
                    if f_val.is_integer():
                        val_str = f"{int(f_val)}"
                    else:
                        val_str = f"{f_val:.1f}"
                except (ValueError, TypeError):
                    val_str = str(val)
            else:
                val_str = str(val)

            parameters.append({
                "type": "text",
                "parameter_name": field,
                "text": val_str
            })

        # Strict local validation check
        if len(parameters) != 21:
            raise ValueError(
                f"Template 'wageslip' requires 21 parameters but generated {len(parameters)}"
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": self.template_name,
                "language": {"code": self.template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": parameters,
                    }
                ],
            },
        }

        # Print debug template information to console
        print(f"Template: {self.template_name}")
        print(f"Language: {self.template_language}\n")
        for idx, param in enumerate(parameters, 1):
            print(f"{idx} -> {param['text']} (name: {param['parameter_name']})")
        print(f"\nTotal parameters: {len(parameters)}")
        print(f"Entire JSON Payload:\n{json.dumps(payload, indent=2)}")

        return payload

    def send_raw_text(self, phone: str, record: Any) -> dict:
        """Send a template text message to a specific phone number."""
        try:
            payload = self.build_template_payload(phone, record)
        except ValueError as val_err:
            self.logger.error("Local payload validation failed: %s", val_err)
            return {"success": False, "message_id": "", "error": str(val_err)}

        # Print serialized JSON immediately before the POST request (Step 6)
        serialized_json = json.dumps(payload, indent=2)
        print("\n--- SENDING METADATA & PAYLOAD ---")
        print(f"API URL: {self.api_url}")
        print(f"Serialized JSON Payload sent over HTTP:\n{serialized_json}")
        print("-----------------------------------\n")

        self.logger.info("Sending template text message to %s", phone)
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Print full HTTP response body (Step 4)
            print("\n--- META GRAPH API RESPONSE ---")
            print(f"HTTP Response Code: {response.status_code}")
            try:
                print(f"Response Body:\n{json.dumps(response.json(), indent=2)}")
            except Exception:
                print(f"Response Body:\n{response.text}")
            print("--------------------------------\n")
            
            if response.status_code in (200, 201):
                response_data = response.json()
                msg_id = response_data.get("messages", [{}])[0].get("id", "")
                return {"success": True, "message_id": msg_id, "error": ""}
                
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text
                
            return {"success": False, "message_id": "", "error": f"HTTP {response.status_code}: {error_msg}"}
        except Exception as e:
            return {"success": False, "message_id": "", "error": str(e)}

    def send_raw_pdf(self, phone: str, media_id: str, workman_id: str, month: str) -> dict:
        """Send a document message with media ID to a specific phone number."""
        filename = f"{workman_id}_WageSlip_{month.replace(' ', '_')}.pdf"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename,
                "caption": self.pdf_caption
            }
        }
        
        # Print serialized JSON immediately before the POST request (Step 6)
        serialized_json = json.dumps(payload, indent=2)
        print("\n--- SENDING METADATA & PAYLOAD ---")
        print(f"API URL: {self.api_url}")
        print(f"Serialized JSON Payload sent over HTTP:\n{serialized_json}")
        print("-----------------------------------\n")

        self.logger.info("Sending PDF document message to %s using media_id=%s", phone, media_id)
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Print full HTTP response body (Step 4)
            print("\n--- META GRAPH API RESPONSE ---")
            print(f"HTTP Response Code: {response.status_code}")
            try:
                print(f"Response Body:\n{json.dumps(response.json(), indent=2)}")
            except Exception:
                print(f"Response Body:\n{response.text}")
            print("--------------------------------\n")

            if response.status_code in (200, 201):
                response_data = response.json()
                msg_id = response_data.get("messages", [{}])[0].get("id", "")
                return {"success": True, "message_id": msg_id, "error": ""}
                
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text
                
            return {"success": False, "message_id": "", "error": f"HTTP {response.status_code}: {error_msg}"}
        except Exception as e:
            return {"success": False, "message_id": "", "error": str(e)}

    # ------------------------------------------------------------------
    # Batch Processing with retry, rate limiting, and database updates
    # ------------------------------------------------------------------

    def send_text_with_retry_and_db_logging(self, record_id: int) -> tuple[bool, str]:
        """Perform text message sending with rate limiter, exponential back-off retries, and database logging."""
        session = get_session()
        record = session.query(PayrollRecord).filter_by(id=record_id).first()
        if not record:
            session.close()
            return False, "Payroll record not found."

        phone_normalized, phone_valid, phone_error = normalize_phone(record.uan if record.uan else "")
        # Fall back to main phone number in record
        if not phone_valid or not phone_normalized:
            phone_normalized, phone_valid, phone_error = normalize_phone(record.bank_account if record.bank_account else "") # wait - actual phone number column
        # In our SQLite schema we stored: workman_id, phone, designation (wait, phone is in employees and was parsed in excel)
        # Let's query employee's phone to check
        employee = record.employee
        phone = record.uan # wait, let's verify where phone number is stored in consolidated table
        # In models.py we have: workmen_id, and details like guardian_name, designation, uan, bank_account. Let's look up record.uan or check Employee.phone
        # In our database schema we stored: employee.phone
        # Wait, let's look at models.py.
        # Employee table has: workman_id, name, phone, designation, uan, bank_account, guardian_name
        # PayrollRecord table has: workman_id, employee_name (which is a string), and uan, bank_account... wait!
        # Does PayrollRecord have a `phone` column? No, we didn't add phone to PayrollRecord, it is in Employee!
        # Ah, we can lookup employee.phone using: record.employee.phone! That is perfect.
        
        target_phone = employee.phone if employee else ""
        if not target_phone:
            record.text_status = "Failed"
            record.text_error = "No phone number configured on employee profile."
            record.text_attempts += 1
            record.text_last_sent = datetime.now()
            session.commit()
            session.close()
            return False, "No phone number."

        phone_normalized, phone_valid, phone_error = normalize_phone(target_phone)
        if not phone_valid:
            record.text_status = "Failed"
            record.text_error = f"Invalid phone format: {phone_error}"
            record.text_attempts += 1
            record.text_last_sent = datetime.now()
            session.commit()
            session.close()
            return False, f"Invalid phone: {phone_error}"

        max_retries = int(SettingsManager.get("RETRY_COUNT", "3"))
        retry_delay = float(SettingsManager.get("RETRY_DELAY", "2.0"))
        
        result = {"success": False, "message_id": "", "error": "Attempt limit reached"}
        
        for attempt in range(1, max_retries + 1):
            # Apply rate limiter
            self._rate_limiter.acquire()
            
            record.text_attempts += 1
            record.text_last_sent = datetime.now()
            session.commit()
            
            # Send
            result = self.send_raw_text(phone_normalized, record)
            
            if result["success"]:
                record.text_status = "Success"
                record.text_message_id = result["message_id"]
                record.text_error = ""
                session.commit()
                session.close()
                return True, "Success"
                
            error = result["error"]
            record.text_error = error
            record.text_status = "Failed"
            session.commit()
            
            # Check for non-retriable codes
            is_non_retriable = any(f"HTTP {code}" in error for code in self.NON_RETRIABLE_CODES)
            if is_non_retriable:
                self.logger.error("Non-retriable WhatsApp send error: %s", error)
                break
                
            # If HTTP 429, inform rate limiter
            if "HTTP 429" in error:
                self._rate_limiter.report_rate_limit()
                
            if attempt < max_retries:
                # Exponential backoff
                delay = RateLimiter.get_backoff_delay(attempt - 1, base_delay=retry_delay)
                self.logger.info("Retrying text send in %.2f seconds (attempt %d)...", delay, attempt + 1)
                time.sleep(delay)

        session.close()
        return False, result["error"]

    def send_pdf_with_retry_and_db_logging(self, record_id: int) -> tuple[bool, str]:
        """Perform PDF media upload, document message sending, rate limiting, retries, and database logging."""
        session = get_session()
        record = session.query(PayrollRecord).filter_by(id=record_id).first()
        if not record:
            session.close()
            return False, "Payroll record not found."

        # Verify PDF file exists
        pdf_path = record.pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            record.pdf_status = "Failed"
            record.pdf_error = "PDF file has not been generated or does not exist."
            record.pdf_attempts += 1
            record.pdf_last_sent = datetime.now()
            session.commit()
            session.close()
            return False, "PDF file missing."

        employee = record.employee
        target_phone = employee.phone if employee else ""
        if not target_phone:
            record.pdf_status = "Failed"
            record.pdf_error = "No phone number configured on employee profile."
            record.pdf_attempts += 1
            record.pdf_last_sent = datetime.now()
            session.commit()
            session.close()
            return False, "No phone number."

        phone_normalized, phone_valid, phone_error = normalize_phone(target_phone)
        if not phone_valid:
            record.pdf_status = "Failed"
            record.pdf_error = f"Invalid phone format: {phone_error}"
            record.pdf_attempts += 1
            record.pdf_last_sent = datetime.now()
            session.commit()
            session.close()
            return False, f"Invalid phone: {phone_error}"

        max_retries = int(SettingsManager.get("RETRY_COUNT", "3"))
        retry_delay = float(SettingsManager.get("RETRY_DELAY", "2.0"))
        
        result = {"success": False, "message_id": "", "error": "Attempt limit reached"}
        media_id = ""

        # Flow: upload media then send
        for attempt in range(1, max_retries + 1):
            self._rate_limiter.acquire()
            
            record.pdf_attempts += 1
            record.pdf_last_sent = datetime.now()
            session.commit()
            
            try:
                # 1. Upload Media
                if not media_id:
                    media_id = self.upload_pdf_media(pdf_path)
                
                # 2. Send Document Message
                result = self.send_raw_pdf(phone_normalized, media_id, record.workman_id, record.month)
                
                if result["success"]:
                    record.pdf_status = "Success"
                    record.pdf_message_id = result["message_id"]
                    record.pdf_error = ""
                    session.commit()
                    session.close()
                    return True, "Success"
                    
                error = result["error"]
                record.pdf_error = error
                record.pdf_status = "Failed"
                session.commit()
                
            except Exception as e:
                error = str(e)
                record.pdf_error = error
                record.pdf_status = "Failed"
                session.commit()
                
            # If HTTP 429, inform rate limiter
            if "HTTP 429" in error:
                self._rate_limiter.report_rate_limit()

            is_non_retriable = any(f"HTTP {code}" in error for code in self.NON_RETRIABLE_CODES)
            if is_non_retriable:
                self.logger.error("Non-retriable WhatsApp document send error: %s", error)
                break

            if attempt < max_retries:
                delay = RateLimiter.get_backoff_delay(attempt - 1, base_delay=retry_delay)
                self.logger.info("Retrying PDF send in %.2f seconds (attempt %d)...", delay, attempt + 1)
                time.sleep(delay)

        session.close()
        return False, result.get("error", "Failed")
