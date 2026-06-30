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

    # Reusable dynamic parameter mapping dictionary (Requirement 4)
    TEMPLATE_FIELD_MAP = {
        "month_year": lambda r: f"{r.month} {r.year}" if hasattr(r, "month") and hasattr(r, "year") and r.month and r.year else getattr(r, "month_year", ""),
        "establishment": lambda r: getattr(r, "establishment", ""),
        "principal_employer": lambda r: getattr(r, "principal_employer", ""),
        "address": lambda r: getattr(r, "address", ""),
        "employee_name": lambda r: getattr(r, "employee_name", ""),
        "workman_id": lambda r: getattr(r, "workman_id", ""),
        "guardian_name": lambda r: getattr(r, "guardian_name", ""),
        "designation": lambda r: getattr(r, "designation", ""),
        "uan": lambda r: getattr(r, "uan", ""),
        "bank_account": lambda r: getattr(r, "bank_account", ""),
        "wage_period": lambda r: getattr(r, "wage_period", ""),
        "attendance": lambda r: getattr(r, "attendance", ""),
        "basic": lambda r: getattr(r, "basic", ""),
        "da": lambda r: getattr(r, "da", ""),
        "allowances": lambda r: getattr(r, "allowances", ""),
        "gross_wages": lambda r: getattr(r, "gross_wages", ""),
        "pf": lambda r: getattr(r, "pf", ""),
        "esi": lambda r: getattr(r, "esi", ""),
        "other_deductions": lambda r: getattr(r, "other_deductions", ""),
        "net_wages": lambda r: getattr(r, "net_wages", ""),
        "issue_date": lambda r: getattr(r, "issue_date", ""),
    }

    def __init__(self) -> None:
        self.logger = setup_logger(__name__)
        
        # Load configurations from settings database
        self.access_token = SettingsManager.get("ACCESS_TOKEN", "")
        self.phone_number_id = SettingsManager.get("PHONE_NUMBER_ID", "")
        self.business_account_id = SettingsManager.get("BUSINESS_ACCOUNT_ID", "")
        self.api_version = SettingsManager.get("API_VERSION", "v25.0")
        
        self.template_name = SettingsManager.get("TEMPLATE_NAME", "wageslip")
        self.pdf_template_name = SettingsManager.get("PDF_TEMPLATE_NAME", "wageslip_pdf")
        self.template_language = SettingsManager.get("TEMPLATE_LANGUAGE", "en")
        
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
        self._template_cache = {}

    def validate_credentials(self) -> tuple[bool, str]:
        """Verify that the configured WhatsApp API credentials and templates are valid.

        Fetches WABA templates from Meta and performs structural validation.
        """
        status_lines = []
        token_valid = False
        phone_id_valid = False
        text_temp_ok = False
        pdf_temp_ok = False
        header_ok = False
        param_count_ok = False
        lang_ok = False

        if not self.access_token:
            status_lines.append("✗ API Token: Missing")
            return False, "\n".join(status_lines)
        if not self.phone_number_id:
            status_lines.append("✗ Phone Number ID: Missing")
            return False, "\n".join(status_lines)

        # 1. API Token & Phone ID checks
        validation_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        self.logger.info("Validating credentials against %s", validation_url)
        try:
            response = requests.get(validation_url, headers=headers, timeout=20)
            self.logger.info("Validation response status: %d", response.status_code)
            if response.status_code == 200:
                token_valid = True
                phone_id_valid = True
                status_lines.append("✓ API Token: Valid")
                status_lines.append("✓ Phone Number ID: Valid")
                status_lines.append(f"✓ API Version: {self.api_version}")
            else:
                status_lines.append("✗ API Token or Phone Number ID invalid")
                try:
                    err_msg = response.json().get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                status_lines.append(f"Details: {err_msg}")
                return False, "\n".join(status_lines)
        except Exception as exc:
            self.logger.error("Credential validation failed: %s", exc)
            status_lines.append("✗ Network connection failed")
            status_lines.append(f"Details: {str(exc)}")
            return False, "\n".join(status_lines)

        # 2. Template verification
        if not self.business_account_id:
            status_lines.append("✗ Business Account ID: Missing (cannot verify templates)")
            return False, "\n".join(status_lines)

        templates_url = f"https://graph.facebook.com/{self.api_version}/{self.business_account_id}/message_templates"
        self.logger.info("Fetching templates from WABA %s", self.business_account_id)

        try:
            # Query Text Template
            resp_text = requests.get(templates_url, headers=headers, params={"name": self.template_name}, timeout=20)
            if resp_text.status_code == 200:
                temps = resp_text.json().get("data", [])
                if any(t.get("name") == self.template_name for t in temps):
                    text_temp_ok = True
                    status_lines.append(f"✓ Text Template: {self.template_name} exists")
                else:
                    status_lines.append(f"✗ Text Template: {self.template_name} not found")
            else:
                status_lines.append(f"✗ Text Template check failed (HTTP {resp_text.status_code})")

            # Query PDF Template
            resp_pdf = requests.get(templates_url, headers=headers, params={"name": self.pdf_template_name}, timeout=20)
            if resp_pdf.status_code == 200:
                temps = resp_pdf.json().get("data", [])
                pdf_t = next((t for t in temps if t.get("name") == self.pdf_template_name), None)
                if pdf_t:
                    pdf_temp_ok = True
                    status_lines.append(f"✓ PDF Template: {self.pdf_template_name} exists")

                    # Validate Status
                    p_status = pdf_t.get("status", "")
                    if p_status.upper() == "APPROVED":
                        status_lines.append(f"✓ Status: APPROVED")
                    else:
                        pdf_temp_ok = False
                        status_lines.append(f"✗ Status: {p_status} (must be APPROVED)")

                    # Validate Language
                    p_lang = pdf_t.get("language", "")
                    if p_lang == "en":
                        lang_ok = True
                        status_lines.append("✓ Language: en")
                    else:
                        status_lines.append(f"✗ Language: {p_lang} (must be en)")

                    # Check components
                    components = pdf_t.get("components", [])

                    # Header check
                    header_c = next((c for c in components if c.get("type", "").upper() == "HEADER"), None)
                    if header_c:
                        h_format = header_c.get("format", "")
                        if h_format.upper() == "DOCUMENT":
                            header_ok = True
                            status_lines.append("✓ PDF Header Type: DOCUMENT")
                        else:
                            status_lines.append(f"✗ PDF Header Type: {h_format} (must be DOCUMENT)")
                    else:
                        status_lines.append("✗ PDF Header Type: Missing header component")

                    # Body check (Requirement 2 & 3)
                    body_c = next((c for c in components if c.get("type", "").upper() == "BODY"), None)
                    if body_c:
                        body_text = body_c.get("text", "")
                        import re
                        variables = re.findall(r"\{\{([a-zA-Z0-9_-]+)\}\}", body_text)
                        
                        # Validate placeholder mappings (Requirement 4)
                        unknown_vars = []
                        for var in variables:
                            if var.isdigit():
                                idx = int(var) - 1
                                if not (0 <= idx < len(self.TEMPLATE_FIELDS)):
                                    unknown_vars.append(var)
                            else:
                                if var not in self.TEMPLATE_FIELD_MAP:
                                    unknown_vars.append(var)
                                    
                        if unknown_vars:
                            pdf_temp_ok = False
                            status_lines.append("\n✗ Unknown placeholder:")
                            for uv in unknown_vars:
                                status_lines.append(uv)
                        else:
                            # Format variables list (Requirement 3)
                            status_lines.append(f"\n✓ BODY Variables ({len(variables)})")
                            for idx, var in enumerate(variables, 1):
                                status_lines.append(f"{idx}. {var}")
                            
                            # Validate expected PDF template structure (Requirement 5)
                            if len(variables) != 2:
                                status_lines.append(f"\n✗ PDF Body Parameter Count: {len(variables)} (must be exactly 2)")
                                pdf_temp_ok = False
                            else:
                                def resolve_name(var):
                                    if var.isdigit():
                                        return self.TEMPLATE_FIELDS[int(var) - 1]
                                    return var

                                resolved_first = resolve_name(variables[0])
                                resolved_second = resolve_name(variables[1])

                                first_ok = (resolved_first == "employee_name" or variables[0] == "1")
                                second_ok = (resolved_second == "month_year" or variables[1] == "2")

                                if first_ok and second_ok:
                                    param_count_ok = True
                                else:
                                    pdf_temp_ok = False
                                    if not first_ok:
                                        status_lines.append(f"\n✗ PDF First Placeholder: {variables[0]} (must resolve to employee_name)")
                                    if not second_ok:
                                        status_lines.append(f"\n✗ PDF Second Placeholder: {variables[1]} (must resolve to month_year)")
                    else:
                        status_lines.append("✗ PDF Body Parameters: Missing body component")
                else:
                    status_lines.append(f"✗ PDF Template: {self.pdf_template_name} not found")
            else:
                status_lines.append(f"✗ PDF Template check failed (HTTP {resp_pdf.status_code})")

            overall_success = (
                token_valid and phone_id_valid and text_temp_ok and
                pdf_temp_ok and header_ok and param_count_ok and lang_ok
            )
            return overall_success, "\n".join(status_lines)

        except Exception as exc:
            self.logger.error("Template query exception: %s", exc)
            status_lines.append(f"✗ Template verification exception: {str(exc)}")
            return False, "\n".join(status_lines)

    def fetch_template_definition(self, name: str) -> dict:
        """Download template definition from Meta Graph API (Requirement 2)."""
        if name in self._template_cache:
            return self._template_cache[name]

        if not self.access_token or not self.business_account_id:
            raise ValueError("Access Token and Business Account ID are required to fetch templates.")
            
        url = f"https://graph.facebook.com/{self.api_version}/{self.business_account_id}/message_templates"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "name": name
        }
        self.logger.info("Fetching template definition for '%s' from Meta", name)
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            temps = response.json().get("data", [])
            matching = [t for t in temps if t.get("name") == name]
            if matching:
                self._template_cache[name] = matching[0]
                return matching[0]
        raise ValueError(f"Failed to fetch template '{name}' from Meta (HTTP {response.status_code}): {response.text}")

    def resolve_template_body_parameters(self, record: Any, template_def: dict) -> list[dict]:
        """Parse variables from template definition BODY component, resolve values, and return ordered parameters (Requirement 1 & 8)."""
        components = template_def.get("components", [])
        body_comp = next((c for c in components if c.get("type", "").upper() == "BODY"), None)
        if not body_comp:
            raise ValueError("Template definition is missing BODY component")
            
        body_text = body_comp.get("text", "")
        import re
        # Find all placeholders like {{variable_name}} or {{1}}
        variables = re.findall(r"\{\{([a-zA-Z0-9_-]+)\}\}", body_text)
        
        resolved_log = []
        parameters = []
        for var in variables:
            val_str = self.resolve_field_value(record, var)
            resolved_log.append(f"{var} -> {val_str}")
            
            parameters.append({
                "type": "text",
                "parameter_name": var,
                "text": val_str
            })
            
        # Logging layout exactly as requested by Requirement 8
        self.logger.debug("==========================================")
        self.logger.debug("Template Name: %s", template_def.get('name', ''))
        self.logger.debug("Template Language: %s", template_def.get('language', ''))
        self.logger.debug("Template Status: %s", template_def.get('status', ''))
        self.logger.debug("Raw BODY Text:\n%s", body_text)
        self.logger.debug("Variables Found:\n[%s]", ",\n".join(variables))
        self.logger.debug("Resolved Values:")
        for r_line in resolved_log:
            parts = r_line.split(" -> ", 1)
            if len(parts) == 2:
                self.logger.debug("%s -> ***MASKED***", parts[0])
            else:
                self.logger.debug(r_line)
        self.logger.debug("Final WhatsApp Parameters:")
        formatted_params = []
        for p in parameters:
            formatted_params.append({
                "type": p["type"],
                "text": "***MASKED***"
            })
        self.logger.debug(json.dumps(formatted_params, indent=2))
        self.logger.debug("==========================================")
        
        return parameters

    def resolve_field_value(self, record: Any, var: str) -> str:
        """Resolve a variable name or position from record, formatting cleanly (Requirement 4 & 9)."""
        if var.isdigit():
            idx = int(var) - 1
            if 0 <= idx < len(self.TEMPLATE_FIELDS):
                field_name = self.TEMPLATE_FIELDS[idx]
            else:
                raise ValueError(f"Template positional index {var} is out of bounds (max {len(self.TEMPLATE_FIELDS)})")
        else:
            field_name = var

        if field_name not in self.TEMPLATE_FIELD_MAP:
            raise ValueError(f"Placeholder '{field_name}' has no resolver mapping.")

        resolver = self.TEMPLATE_FIELD_MAP[field_name]
        try:
            val = resolver(record)
        except Exception as e:
            raise ValueError(f"Failed to resolve placeholder '{field_name}': {str(e)}")

        is_empty = False
        if val is None:
            is_empty = True
        else:
            # Format numeric or text values cleanly
            if field_name in ("basic", "da", "allowances", "gross_wages", "pf", "esi", "other_deductions", "net_wages"):
                try:
                    f_val = float(val)
                    if f_val.is_integer():
                        val_str = f"{int(f_val)}"
                    else:
                        val_str = f"{f_val:.2f}"
                except (ValueError, TypeError):
                    val_str = str(val)
            elif field_name == "attendance":
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

            if not val_str or not val_str.strip():
                is_empty = True

        if is_empty:
            optional_fields = {
                "workman_id", "uan", "guardian_name", "designation", "bank_account",
                "establishment", "principal_employer", "address", "wage_period", "issue_date"
            }
            if field_name in optional_fields:
                placeholder = SettingsManager.get("OPTIONAL_FIELD_PLACEHOLDER", "-")
                if not placeholder or not placeholder.strip():
                    placeholder = "-"
                val_str = placeholder
            else:
                raise ValueError(f"Resolved value for placeholder '{field_name}' is empty.")

        return val_str

    def upload_pdf_media(self, pdf_path: str, custom_filename: Optional[str] = None) -> str:
        """Upload a PDF file using Meta Media API and return the media_id string on success."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found for upload: {pdf_path}")
            
        self.logger.info("Uploading PDF to WhatsApp Media API: %s", pdf_path)
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        filename = custom_filename if custom_filename else os.path.basename(pdf_path)
        
        data = {
            "messaging_product": "whatsapp",
            "type": "document"
        }
        
        try:
            with open(pdf_path, "rb") as f_in:
                files = {
                    "file": (filename, f_in, "application/pdf")
                }
                response = requests.post(
                    self.media_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60
                )
            
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

    def build_template_payload(self, phone: str, record: Any, template_def: Optional[dict] = None) -> dict:
        """Build WhatsApp Cloud API template-message payload using dynamic variable resolution."""
        is_fallback = False
        if not template_def:
            is_fallback = True
            # Fallback to local positional template structure if definition is not provided
            placeholders = " ".join([f"{{{{{i}}}}}" for i in range(1, 22)])
            template_def = {
                "name": self.template_name,
                "components": [
                    {
                        "type": "BODY",
                        "text": placeholders
                    }
                ]
            }

        parameters = self.resolve_template_body_parameters(record, template_def)

        # Strict local validation check (only for fallback positional wageslip template)
        if is_fallback and len(parameters) != 21:
            raise ValueError(
                f"Template '{self.template_name}' requires 21 parameters but generated {len(parameters)}"
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_def.get("name", self.template_name),
                "language": {"code": self.template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": parameters,
                    }
                ],
            },
        }
        return payload

    def _mask_payload(self, payload: dict) -> str:
        """Create a deep copy of payload and mask all sensitive values for safe logging."""
        import copy
        try:
            payload_copy = copy.deepcopy(payload)
            # Mask recipient phone number
            if "to" in payload_copy:
                to_val = str(payload_copy["to"])
                payload_copy["to"] = to_val[:3] + "******" + to_val[-3:] if len(to_val) > 6 else "******"
            
            # Mask parameters inside components
            components = payload_copy.get("template", {}).get("components", [])
            for comp in components:
                params = comp.get("parameters", [])
                for param in params:
                    if "text" in param:
                        param["text"] = "***MASKED***"
                    if "document" in param:
                        doc = param["document"]
                        if "filename" in doc:
                            doc["filename"] = "***MASKED***"
                        if "id" in doc:
                            doc["id"] = "***MASKED_ID***"
            return json.dumps(payload_copy, indent=2)
        except Exception:
            return "{\n  \"masked_error\": \"could not mask payload\"\n}"

    def send_raw_text(self, phone: str, record: Any, template_def: Optional[dict] = None) -> dict:
        """Send a template text message to a specific phone number."""
        try:
            payload = self.build_template_payload(phone, record, template_def=template_def)
        except ValueError as val_err:
            self.logger.error("Local payload validation failed: %s", val_err)
            return {"success": False, "message_id": "", "error": str(val_err)}

        # Logging metadata and payload immediately before the POST request
        serialized_json = self._mask_payload(payload)
        self.logger.debug("--- SENDING METADATA & PAYLOAD ---")
        self.logger.debug("API URL: %s", self.api_url)
        self.logger.debug("Serialized JSON Payload sent over HTTP:\n%s", serialized_json)
        self.logger.debug("-----------------------------------")

        self.logger.info("Sending template text message to %s", phone)
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Logging full HTTP response body
            self.logger.debug("--- META GRAPH API RESPONSE ---")
            self.logger.debug("HTTP Response Code: %d", response.status_code)
            try:
                self.logger.debug("Response Body:\n%s", json.dumps(response.json(), indent=2))
            except Exception:
                self.logger.debug("Response Body:\n%s", response.text)
            self.logger.debug("--------------------------------")
            
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

    def build_pdf_template_payload(
        self,
        phone: str,
        template_name: str,
        media_id: str,
        filename: str,
        employee_name: str,
        month_year: str,
        template_def: Optional[dict] = None
    ) -> dict:
        """Build WhatsApp Cloud API payload for a Document Template message (Requirement 5 & 7)."""
        if not template_name:
            raise ValueError("PDF template name is empty or not configured.")
        if not media_id:
            raise ValueError("media_id is empty or missing.")
        if not employee_name or not employee_name.strip():
            raise ValueError("employee_name is empty or invalid.")
        if not month_year or not month_year.strip():
            raise ValueError("month_year is empty or invalid.")
        if not filename or not filename.strip():
            raise ValueError("filename is empty or invalid.")

        # Create dummy record for the template parameter mapping resolver
        class DummyRecord:
            def __init__(self, emp_name, m_yr):
                self.employee_name = emp_name
                self.month_year = m_yr
                parts = m_yr.split()
                self.month = parts[0] if parts else ""
                self.year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else ""

        record = DummyRecord(employee_name, month_year)

        if not template_def:
            # Fallback to local named template structure if definition is not provided
            template_def = {
                "name": template_name,
                "components": [
                    {
                        "type": "BODY",
                        "text": "Hello {{employee_name}} your slip for {{month_year}}"
                    }
                ]
            }

        body_parameters = self.resolve_template_body_parameters(record, template_def)

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": self.template_language},
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "document",
                                "document": {
                                    "id": media_id,
                                    "filename": filename
                                }
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": body_parameters
                    }
                ]
            }
        }
        return payload

    def send_raw_pdf_template(
        self,
        phone: str,
        template_name: str,
        media_id: str,
        filename: str,
        employee_name: str,
        month_year: str,
        template_def: Optional[dict] = None
    ) -> dict:
        """Send a document template message to a specific phone number."""
        try:
            payload = self.build_pdf_template_payload(
                phone=phone,
                template_name=template_name,
                media_id=media_id,
                filename=filename,
                employee_name=employee_name,
                month_year=month_year,
                template_def=template_def
            )
        except ValueError as val_err:
            self.logger.error("Local payload validation failed for PDF template: %s", val_err)
            return {"success": False, "message_id": "", "error": str(val_err)}

        # Logging payload (Requirement 8)
        serialized_json = self._mask_payload(payload)
        self.logger.debug("--- SENDING METADATA & PAYLOAD ---")
        self.logger.debug("API URL: %s", self.api_url)
        self.logger.debug("Serialized JSON Payload sent over HTTP:\n%s", serialized_json)
        self.logger.debug("-----------------------------------")

        self.logger.info("Sending PDF template message to %s using media_id=%s", phone, media_id)
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            self.logger.debug("--- META GRAPH API RESPONSE ---")
            self.logger.debug("HTTP Response Code: %d", response.status_code)
            try:
                resp_json = response.json()
                self.logger.debug("Response Body:\n%s", json.dumps(resp_json, indent=2))
            except Exception:
                resp_json = {}
                self.logger.debug("Response Body:\n%s", response.text)
            self.logger.debug("--------------------------------")
            
            if response.status_code in (200, 201):
                msg_id = resp_json.get("messages", [{}])[0].get("id", "")
                return {"success": True, "message_id": msg_id, "error": ""}
                
            try:
                error_data = resp_json if resp_json else response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                meta_code = error_data.get("error", {}).get("code", "")
            except Exception:
                error_msg = response.text
                meta_code = ""
                
            # Log Meta specific errors on failure (Requirement 8)
            self.logger.error(
                "WhatsApp API send template error: HTTP %d, Meta Code %s, Message: %s, Body: %s",
                response.status_code, str(meta_code), error_msg, response.text
            )
            return {
                "success": False,
                "message_id": "",
                "error": f"HTTP {response.status_code}: {error_msg}",
                "meta_code": meta_code,
                "response_body": response.text
            }
        except Exception as e:
            return {"success": False, "message_id": "", "error": str(e)}

    # ------------------------------------------------------------------
    # Batch Processing with retry, rate limiting, and database updates
    # ------------------------------------------------------------------

    def send_text_with_retry_and_db_logging(self, record_id: int) -> tuple[bool, str]:
        """Perform text message sending with rate limiter, exponential back-off retries, and database logging."""
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=record_id).first()
            if not record:
                return False, "Payroll record not found."

            # Fetch template definition from Meta at runtime (Requirement 2)
            try:
                template_def = self.fetch_template_definition(self.template_name)
            except Exception as e:
                try:
                    record.text_status = "Failed"
                    record.text_error = f"Failed to fetch template definition: {str(e)}"
                    record.text_attempts += 1
                    record.text_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during template fetch error logging: %s", db_err)
                return False, f"Failed to fetch template: {str(e)}"

            phone_normalized, phone_valid, phone_error = normalize_phone(record.uan if record.uan else "")
            # Fall back to main phone number in record
            if not phone_valid or not phone_normalized:
                phone_normalized, phone_valid, phone_error = normalize_phone(record.bank_account if record.bank_account else "") # wait - actual phone number column
            
            employee = record.employee
            target_phone = employee.phone if employee else ""
            if not target_phone:
                try:
                    record.text_status = "Failed"
                    record.text_error = "No phone number configured on employee profile."
                    record.text_attempts += 1
                    record.text_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during target phone check: %s", db_err)
                return False, "No phone number."

            phone_normalized, phone_valid, phone_error = normalize_phone(target_phone)
            if not phone_valid:
                try:
                    record.text_status = "Failed"
                    record.text_error = f"Invalid phone format: {phone_error}"
                    record.text_attempts += 1
                    record.text_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during phone validation: %s", db_err)
                return False, f"Invalid phone: {phone_error}"

            max_retries = int(SettingsManager.get("RETRY_COUNT", "3"))
            retry_delay = float(SettingsManager.get("RETRY_DELAY", "2.0"))
            
            result = {"success": False, "message_id": "", "error": "Attempt limit reached"}
            
            for attempt in range(1, max_retries + 1):
                # Apply rate limiter
                self._rate_limiter.acquire()
                
                try:
                    record.text_attempts += 1
                    record.text_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during attempt setup: %s", db_err)
                    raise db_err
                
                # Send
                result = self.send_raw_text(phone_normalized, record, template_def=template_def)
                
                try:
                    if result["success"]:
                        record.text_status = "Success"
                        record.text_message_id = result["message_id"]
                        record.text_error = ""
                        session.commit()
                        return True, "Success"
                        
                    error = result["error"]
                    record.text_error = error
                    record.text_status = "Failed"
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during send status logging: %s", db_err)
                    raise db_err
                
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

            return False, result["error"]
        except Exception as e:
            session.rollback()
            self.logger.exception("Failed to complete WhatsApp send process for record %d: %s", record_id, e)
            return False, str(e)
        finally:
            session.close()
    def send_pdf_with_retry_and_db_logging(self, record_id: int) -> tuple[bool, str]:
        """Perform PDF media upload (if needed), document template sending, rate limiting, retries, and database updates."""
        session = get_session()
        try:
            record = session.query(PayrollRecord).filter_by(id=record_id).first()
            if not record:
                return False, "Payroll record not found."

            # Fetch template definition from Meta at runtime (Requirement 2)
            try:
                template_def = self.fetch_template_definition(self.pdf_template_name)
            except Exception as e:
                try:
                    record.pdf_status = "Failed"
                    record.pdf_error = f"Failed to fetch template definition: {str(e)}"
                    record.pdf_attempts += 1
                    record.pdf_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during PDF template fetch error logging: %s", db_err)
                return False, f"Failed to fetch template: {str(e)}"

            # Verify PDF file exists
            pdf_path = record.pdf_path
            if not pdf_path or not os.path.exists(pdf_path):
                try:
                    record.pdf_status = "Failed"
                    record.pdf_error = "PDF file has not been generated or does not exist."
                    record.pdf_attempts += 1
                    record.pdf_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during PDF missing error logging: %s", db_err)
                return False, "PDF file missing."

            employee = record.employee
            target_phone = employee.phone if employee else ""
            if not target_phone:
                try:
                    record.pdf_status = "Failed"
                    record.pdf_error = "No phone number configured on employee profile."
                    record.pdf_attempts += 1
                    record.pdf_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during PDF target phone check: %s", db_err)
                return False, "No phone number."

            phone_normalized, phone_valid, phone_error = normalize_phone(target_phone)
            if not phone_valid:
                try:
                    record.pdf_status = "Failed"
                    record.pdf_error = f"Invalid phone format: {phone_error}"
                    record.pdf_attempts += 1
                    record.pdf_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during PDF phone validation check: %s", db_err)
                return False, f"Invalid phone: {phone_error}"

            max_retries = int(SettingsManager.get("RETRY_COUNT", "3"))
            retry_delay = float(SettingsManager.get("RETRY_DELAY", "2.0"))
            
            result = {"success": False, "message_id": "", "error": "Attempt limit reached"}
            
            # Determine dynamic filename (friendly filename from employee name only)
            import re
            clean_emp_name = re.sub(r"[^a-zA-Z0-9_-]", "_", record.employee_name.strip())
            dynamic_filename = f"{clean_emp_name}.pdf"

            # Check existing media_id from DB record (Requirement 5)
            media_id = record.pdf_media_id or ""

            # Flow: upload media then send
            for attempt in range(1, max_retries + 1):
                self._rate_limiter.acquire()
                
                try:
                    record.pdf_attempts += 1
                    record.pdf_last_sent = datetime.now()
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    self.logger.error("Database update failed during PDF attempt setup: %s", db_err)
                    raise db_err
                
                is_media_error = False
                try:
                    # 1. Upload PDF if we do not have a stored media_id
                    if not media_id:
                        # Logging before upload (Requirement 8)
                        self.logger.info(
                            "Uploading PDF... Employee: %s, Month: %s, Filename: %s, Path: %s",
                            record.employee_name, record.month_year, dynamic_filename, pdf_path
                        )
                        start_time = time.time()
                        media_id = self.upload_pdf_media(pdf_path, custom_filename=dynamic_filename)
                        upload_duration = time.time() - start_time
                        # Logging after upload (Requirement 8)
                        self.logger.info("Media ID: %s (upload duration: %.2f seconds)", media_id, upload_duration)
                        
                        # Store media_id inside the payroll record (Requirement 4)
                        record.pdf_media_id = media_id
                        session.commit()

                    # 2. Send Document Template
                    # Logging before sending (Requirement 8)
                    self.logger.info(
                        "Sending PDF template. Template Name: %s, Employee: %s, Month: %s, Media ID: %s",
                        self.pdf_template_name, record.employee_name, record.month_year, media_id
                    )
                    
                    result = self.send_raw_pdf_template(
                        phone=phone_normalized,
                        template_name=self.pdf_template_name,
                        media_id=media_id,
                        filename=dynamic_filename,
                        employee_name=record.employee_name,
                        month_year=f"{record.month} {record.year}",
                        template_def=template_def
                    )
                    
                    try:
                        if result["success"]:
                            record.pdf_status = "Success"
                            record.pdf_message_id = result["message_id"]
                            record.pdf_error = ""
                            session.commit()
                            
                            # Logging success (Requirement 8)
                            masked_phone = phone_normalized[:5] + "******" + phone_normalized[-2:] if len(phone_normalized) > 7 else phone_normalized
                            self.logger.info(
                                "WhatsApp document template sent successfully. Message ID: %s, Media ID: %s, Template: %s, Employee: %s, Phone: %s",
                                result["message_id"], media_id, self.pdf_template_name, record.employee_name, masked_phone
                            )
                            return True, "Success"
                            
                        # Handle failure
                        error = result["error"]
                        record.pdf_error = error
                        record.pdf_status = "Failed"
                        session.commit()
                    except Exception as db_err:
                        session.rollback()
                        self.logger.error("Database update failed during PDF status logging: %s", db_err)
                        raise db_err
                    
                    # Check for expired/invalid media ID (Requirement 5)
                    if "meta_code" in result and str(result["meta_code"]) in ("100", "131009", "131053"):
                        is_media_error = True
                    elif any(word in error.lower() for word in ("media", "expired", "invalid")):
                        is_media_error = True
                        
                    if is_media_error:
                        self.logger.warning("Stored media ID %s expired or invalid. Clearing it to force re-upload on next attempt.", media_id)
                        media_id = ""
                        try:
                            record.pdf_media_id = None
                            session.commit()
                        except Exception as db_err:
                            session.rollback()
                            self.logger.error("Database update failed during clearing expired media ID: %s", db_err)
                            raise db_err

                except Exception as e:
                    error = str(e)
                    try:
                        record.pdf_error = error
                        record.pdf_status = "Failed"
                        session.commit()
                    except Exception as db_err:
                        session.rollback()
                        self.logger.error("Database update failed during PDF retry exception logging: %s", db_err)
                        raise db_err
                    
                # If HTTP 429, inform rate limiter
                if "HTTP 429" in error:
                    self._rate_limiter.report_rate_limit()

                is_non_retriable = False
                if not is_media_error:
                    is_non_retriable = any(f"HTTP {code}" in error for code in self.NON_RETRIABLE_CODES)
                    
                if is_non_retriable:
                    self.logger.error("Non-retriable WhatsApp document send error: %s", error)
                    break

                if attempt < max_retries:
                    delay = RateLimiter.get_backoff_delay(attempt - 1, base_delay=retry_delay)
                    self.logger.info("Retrying PDF send in %.2f seconds (attempt %d)...", delay, attempt + 1)
                    time.sleep(delay)

            return False, result.get("error", "Failed")
        except Exception as e:
            session.rollback()
            self.logger.exception("Failed to complete WhatsApp PDF send process for record %d: %s", record_id, e)
            return False, str(e)
        finally:
            session.close()
