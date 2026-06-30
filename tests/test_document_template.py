"""Unit and integration tests for WhatsApp PDF document templates refactoring."""

import os
import shutil
import tempfile
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

# Initialize database directory before importing service modules
TEMP_DATA_DIR = tempfile.mkdtemp()
os.environ["PAYROLL_DATA_DIR"] = TEMP_DATA_DIR

from database.db import init_database, get_session
from database.models import Employee, PayrollRecord
from services.whatsapp_service import WhatsAppService
from settings.settings_manager import SettingsManager


class TestWhatsAppDocumentTemplate(unittest.TestCase):
    """Verifies all aspects of Document Template sending, builders, retries, and validations."""

    @classmethod
    def setUpClass(cls):
        init_database()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEMP_DATA_DIR):
            shutil.rmtree(TEMP_DATA_DIR)
        if "PAYROLL_DATA_DIR" in os.environ:
            del os.environ["PAYROLL_DATA_DIR"]

    def setUp(self):
        # Clear tables
        session = get_session()
        session.query(PayrollRecord).delete()
        session.query(Employee).delete()
        session.commit()
        session.close()
        
        self.service = WhatsAppService()
        self.service.access_token = "mock_token"
        self.service.phone_number_id = "mock_phone_id"
        self.service.business_account_id = "mock_biz_id"
        self.service.pdf_template_name = "wageslip_pdf"

    def test_build_pdf_template_payload_valid(self):
        """Verify successful generation of Document Template payloads."""
        payload = self.service.build_pdf_template_payload(
            phone="919876543210",
            template_name="wageslip_pdf",
            media_id="media_12345",
            filename="John_Doe_June_2026.pdf",
            employee_name="John Doe",
            month_year="June 2026"
        )
        
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["to"], "919876543210")
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "wageslip_pdf")
        
        # Verify components
        components = payload["template"]["components"]
        self.assertEqual(len(components), 2)
        
        # Header component checks
        header = components[0]
        self.assertEqual(header["type"], "header")
        self.assertEqual(header["parameters"][0]["type"], "document")
        self.assertEqual(header["parameters"][0]["document"]["id"], "media_12345")
        self.assertEqual(header["parameters"][0]["document"]["filename"], "John_Doe_June_2026.pdf")
        
        # Body component checks
        body = components[1]
        self.assertEqual(body["type"], "body")
        self.assertEqual(body["parameters"][0]["text"], "John Doe")
        self.assertEqual(body["parameters"][1]["text"], "June 2026")

    def test_build_pdf_template_payload_missing_arguments(self):
        """Verify validation errors are raised for missing/invalid build fields."""
        with self.assertRaises(ValueError):
            self.service.build_pdf_template_payload("919876543210", "", "media_123", "fn.pdf", "Name", "June 2026")
        with self.assertRaises(ValueError):
            self.service.build_pdf_template_payload("919876543210", "tpl", "", "fn.pdf", "Name", "June 2026")
        with self.assertRaises(ValueError):
            self.service.build_pdf_template_payload("919876543210", "tpl", "media_123", "", "Name", "June 2026")
        with self.assertRaises(ValueError):
            self.service.build_pdf_template_payload("919876543210", "tpl", "media_123", "fn.pdf", "", "June 2026")
        with self.assertRaises(ValueError):
            self.service.build_pdf_template_payload("919876543210", "tpl", "media_123", "fn.pdf", "Name", "")

    @patch("requests.get")
    def test_validate_credentials_full_reporting(self, mock_get):
        """Verify Test Connection detailed reporting (language, status, params, header)."""
        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "mock_phone_id" in url:
                resp.status_code = 200
                resp.json.return_value = {"id": "mock_phone_id"}
            elif "message_templates" in url:
                resp.status_code = 200
                if params and params.get("name") == self.service.template_name:
                    resp.json.return_value = {"data": [{"name": self.service.template_name}]}
                elif params and params.get("name") == self.service.pdf_template_name:
                    resp.json.return_value = {"data": [{
                        "name": self.service.pdf_template_name,
                        "status": "APPROVED",
                        "language": "en",
                        "components": [
                            {"type": "HEADER", "format": "DOCUMENT"},
                            {"type": "BODY", "text": "Hello {{1}} your slip for {{2}}"}
                        ]
                    }]}
            return resp

        mock_get.side_effect = side_effect
        
        success, msg = self.service.validate_credentials()
        self.assertTrue(success)
        self.assertIn("✓ API Token: Valid", msg)
        self.assertIn("✓ Phone Number ID: Valid", msg)
        self.assertIn("✓ API Version: v25.0", msg)
        self.assertIn("✓ PDF Header Type: DOCUMENT", msg)
        self.assertIn("✓ BODY Variables (2)", msg)
        self.assertIn("1. 1", msg)
        self.assertIn("2. 2", msg)
        self.assertIn("✓ Language: en", msg)

    @patch("requests.get")
    def test_validate_credentials_named_placeholders(self, mock_get):
        """Verify Test Connection succeeds with named placeholders employee_name and month_year."""
        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "mock_phone_id" in url:
                resp.status_code = 200
                resp.json.return_value = {"id": "mock_phone_id"}
            elif "message_templates" in url:
                resp.status_code = 200
                if params and params.get("name") == self.service.template_name:
                    resp.json.return_value = {"data": [{"name": self.service.template_name}]}
                elif params and params.get("name") == self.service.pdf_template_name:
                    resp.json.return_value = {"data": [{
                        "name": self.service.pdf_template_name,
                        "status": "APPROVED",
                        "language": "en",
                        "components": [
                            {"type": "HEADER", "format": "DOCUMENT"},
                            {"type": "BODY", "text": "Hello {{employee_name}} your slip for {{month_year}}"}
                        ]
                    }]}
            return resp

        mock_get.side_effect = side_effect
        success, msg = self.service.validate_credentials()
        self.assertTrue(success)
        self.assertIn("✓ BODY Variables (2)", msg)
        self.assertIn("1. employee_name", msg)
        self.assertIn("2. month_year", msg)

    @patch("requests.get")
    def test_validate_credentials_unknown_placeholder_fails(self, mock_get):
        """Verify Test Connection reports descriptive error for unknown placeholders."""
        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "mock_phone_id" in url:
                resp.status_code = 200
                resp.json.return_value = {"id": "mock_phone_id"}
            elif "message_templates" in url:
                resp.status_code = 200
                if params and params.get("name") == self.service.template_name:
                    resp.json.return_value = {"data": [{"name": self.service.template_name}]}
                elif params and params.get("name") == self.service.pdf_template_name:
                    resp.json.return_value = {"data": [{
                        "name": self.service.pdf_template_name,
                        "status": "APPROVED",
                        "language": "en",
                        "components": [
                            {"type": "HEADER", "format": "DOCUMENT"},
                            {"type": "BODY", "text": "Hello {{employee_name}} your bonus is {{bonus_amount}}"}
                        ]
                    }]}
            return resp

        mock_get.side_effect = side_effect
        success, msg = self.service.validate_credentials()
        self.assertFalse(success)
        self.assertIn("Unknown placeholder:", msg)
        self.assertIn("bonus_amount", msg)

    @patch("requests.get")
    def test_validate_credentials_pdf_structure_mismatch(self, mock_get):
        """Verify Test Connection reports descriptive failure when template is invalid."""
        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "mock_phone_id" in url:
                resp.status_code = 200
                resp.json.return_value = {"id": "mock_phone_id"}
            elif "message_templates" in url:
                resp.status_code = 200
                if params and params.get("name") == self.service.template_name:
                    resp.json.return_value = {"data": [{"name": self.service.template_name}]}
                elif params and params.get("name") == self.service.pdf_template_name:
                    resp.json.return_value = {"data": [{
                        "name": self.service.pdf_template_name,
                        "status": "PENDING", # not approved
                        "language": "de", # de instead of en
                        "components": [
                            {"type": "HEADER", "format": "IMAGE"}, # image instead of document
                            {"type": "BODY", "text": "Hello {{1}}"} # 1 param instead of 2
                        ]
                    }]}
            return resp

        mock_get.side_effect = side_effect
        
        success, msg = self.service.validate_credentials()
        self.assertFalse(success)
        self.assertIn("✗ Status: PENDING", msg)
        self.assertIn("✗ Language: de", msg)
        self.assertIn("✗ PDF Header Type: IMAGE", msg)
        self.assertIn("✗ PDF Body Parameter Count: 1", msg)

    @patch("services.whatsapp_service.WhatsAppService.fetch_template_definition")
    @patch("services.whatsapp_service.WhatsAppService.upload_pdf_media")
    @patch("requests.post")
    def test_send_pdf_smart_retry_workflow(self, mock_post, mock_upload, mock_fetch):
        """Verify smart retries reuse existing media_ids and save metadata on success."""
        mock_fetch.return_value = {
            "name": "wageslip_pdf",
            "components": [
                {"type": "HEADER", "format": "DOCUMENT"},
                {"type": "BODY", "text": "Hello {{employee_name}} your slip for {{month_year}}"}
            ]
        }

        # 1. Mock DB data
        session = get_session()
        emp = Employee(workman_id="EMP_SMART_01", name="Smart Employee", phone="+919876543210")
        session.add(emp)
        session.commit()
        
        # Write dummy file
        temp_file_fd, temp_file_path = tempfile.mkstemp()
        os.close(temp_file_fd)
        
        record = PayrollRecord(
            workman_id="EMP_SMART_01",
            employee_name="Smart Employee",
            month="June",
            year=2026,
            month_year="June 2026",
            pdf_path=temp_file_path,
            pdf_generated=True
        )
        session.add(record)
        session.commit()
        record_id = record.id
        session.close()

        # 2. Mock WhatsApp API success response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "wamid.success_msg_id"}]
        }
        mock_post.return_value = mock_response
        mock_upload.return_value = "media_mocked_id_77"

        # First send (no stored media ID, should trigger upload)
        success, msg = self.service.send_pdf_with_retry_and_db_logging(record_id)
        
        self.assertTrue(success)
        mock_upload.assert_called_once()
        
        # Verify media_id & message_id are saved (Requirement 4)
        session = get_session()
        updated_rec = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertEqual(updated_rec.pdf_media_id, "media_mocked_id_77")
        self.assertEqual(updated_rec.pdf_message_id, "wamid.success_msg_id")
        self.assertEqual(updated_rec.pdf_status, "Success")
        session.close()

        # Second send (media ID exists, should reuse and NOT call upload again)
        mock_upload.reset_mock()
        success2, msg2 = self.service.send_pdf_with_retry_and_db_logging(record_id)
        self.assertTrue(success2)
        mock_upload.assert_not_called()

        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    @patch("services.whatsapp_service.WhatsAppService.fetch_template_definition")
    @patch("services.whatsapp_service.WhatsAppService.upload_pdf_media")
    @patch("requests.post")
    def test_send_pdf_expired_media_forces_reupload(self, mock_post, mock_upload, mock_fetch):
        """Verify expired/invalid media IDs trigger re-upload logic on retry."""
        mock_fetch.return_value = {
            "name": "wageslip_pdf",
            "components": [
                {"type": "HEADER", "format": "DOCUMENT"},
                {"type": "BODY", "text": "Hello {{employee_name}} your slip for {{month_year}}"}
            ]
        }

        session = get_session()
        emp = Employee(workman_id="EMP_EXPIRED_01", name="Expired Employee", phone="+919876543210")
        session.add(emp)
        session.commit()
        
        # Write dummy file
        temp_file_fd, temp_file_path = tempfile.mkstemp()
        os.close(temp_file_fd)
        
        record = PayrollRecord(
            workman_id="EMP_EXPIRED_01",
            employee_name="Expired Employee",
            month="June",
            year=2026,
            month_year="June 2026",
            pdf_path=temp_file_path,
            pdf_generated=True,
            pdf_media_id="old_stale_media_id"
        )
        session.add(record)
        session.commit()
        record_id = record.id
        session.close()

        # Mock first response as expired media error, second attempt succeeds
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 400
        mock_resp_fail.text = '{"error":{"message":"The media ID is expired.","code":100}}'
        mock_resp_fail.json.return_value = {"error": {"message": "The media ID is expired.", "code": 100}}
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {"messages": [{"id": "wamid.retry_success"}]}
        
        mock_post.side_effect = [mock_resp_fail, mock_resp_success]
        mock_upload.return_value = "new_fresh_media_id"

        # Trigger send
        success, msg = self.service.send_pdf_with_retry_and_db_logging(record_id)
        
        self.assertTrue(success)
        # Should have called upload once to resolve expired media ID
        mock_upload.assert_called_once()
        
        # Verify db is updated with the new successfully sent details
        session = get_session()
        updated_rec = session.query(PayrollRecord).filter_by(id=record_id).first()
        self.assertEqual(updated_rec.pdf_media_id, "new_fresh_media_id")
        self.assertEqual(updated_rec.pdf_message_id, "wamid.retry_success")
        self.assertEqual(updated_rec.pdf_status, "Success")
        session.close()

        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    def test_variable_extraction_and_mixed_ordering(self):
        """Test extraction of mixed variables from BODY text and order preservation."""
        template_def = {
            "name": "wageslip_pdf",
            "components": [
                {"type": "BODY", "text": "Dear {{employee_name}}, here is your code {{workman_id}} for {{month_year}}."}
            ]
        }
        class DummyRecord:
            employee_name = "Alice Smith"
            workman_id = "EMP999"
            month = "August"
            year = 2026

        params = self.service.resolve_template_body_parameters(DummyRecord(), template_def)
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0]["parameter_name"], "employee_name")
        self.assertEqual(params[0]["text"], "Alice Smith")
        self.assertEqual(params[1]["parameter_name"], "workman_id")
        self.assertEqual(params[1]["text"], "EMP999")
        self.assertEqual(params[2]["parameter_name"], "month_year")
        self.assertEqual(params[2]["text"], "August 2026")

    def test_positional_template_resolution(self):
        """Test positional template resolution mapping to index in TEMPLATE_FIELDS."""
        template_def = {
            "name": "wageslip",
            "components": [
                {"type": "BODY", "text": "Slip: {{1}} | {{5}} | {{6}}"}
            ]
        }
        class DummyRecord:
            month = "September"
            year = 2026
            employee_name = "Bob Marley"
            workman_id = "EMP888"

        params = self.service.resolve_template_body_parameters(DummyRecord(), template_def)
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0]["parameter_name"], "1")
        self.assertEqual(params[0]["text"], "September 2026")
        self.assertEqual(params[1]["parameter_name"], "5")
        self.assertEqual(params[1]["text"], "Bob Marley")
        self.assertEqual(params[2]["parameter_name"], "6")
        self.assertEqual(params[2]["text"], "EMP888")

    def test_resolver_missing_mappings_error(self):
        """Test resolver raises ValueError for template fields not supported/mapped."""
        template_def = {
            "name": "wageslip",
            "components": [
                {"type": "BODY", "text": "Field: {{unsupported_variable_name}}"}
            ]
        }
        class DummyRecord:
            pass

        with self.assertRaises(ValueError) as ctx:
            self.service.resolve_template_body_parameters(DummyRecord(), template_def)
        self.assertIn("has no resolver mapping", str(ctx.exception))

    def test_resolver_empty_values_error(self):
        """Test resolver raises ValueError when resolved values are empty or None."""
        template_def = {
            "name": "wageslip_pdf",
            "components": [
                {"type": "BODY", "text": "Hello {{employee_name}}"}
            ]
        }
        class DummyRecord:
            employee_name = ""

        with self.assertRaises(ValueError) as ctx:
            self.service.resolve_template_body_parameters(DummyRecord(), template_def)
        self.assertIn("is empty", str(ctx.exception))

    @patch("services.whatsapp_service.WhatsAppService.fetch_template_definition")
    @patch("requests.post")
    def test_send_text_with_runtime_fetching(self, mock_post, mock_fetch):
        """Test that send_text_with_retry_and_db_logging downloads template and succeeds."""
        # 1. Mock DB data
        session = get_session()
        emp = Employee(workman_id="EMP_TEXT_01", name="Text Employee", phone="+919876543210")
        session.add(emp)
        session.commit()
        
        record = PayrollRecord(
            workman_id="EMP_TEXT_01",
            employee_name="Text Employee",
            month="June",
            year=2026,
            month_year="June 2026",
            pdf_path="dummy.pdf"
        )
        session.add(record)
        session.commit()
        record_id = record.id
        session.close()

        # 2. Mock Template fetch
        mock_fetch.return_value = {
            "name": "wageslip",
            "components": [
                {"type": "BODY", "text": "Hello {{employee_name}} slip for {{month_year}}"}
            ]
        }

        # 3. Mock POST
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.text_success_1"}]}
        mock_post.return_value = mock_response

        # Trigger send
        success, msg = self.service.send_text_with_retry_and_db_logging(record_id)
        self.assertTrue(success)
        mock_fetch.assert_called_once_with(self.service.template_name)


if __name__ == "__main__":
    unittest.main()
