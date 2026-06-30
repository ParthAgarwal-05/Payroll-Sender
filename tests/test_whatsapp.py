"""Mock unit tests for WhatsApp Cloud API and Media API integrations."""

import unittest
from unittest.mock import patch, MagicMock

# Initialize DB first in tests to allow settings lookups
from database.db import init_database
init_database()

from services.whatsapp_service import WhatsAppService


class TestWhatsAppService(unittest.TestCase):
    """Mocks network requests to verify Meta API client operations."""

    @patch("requests.get")
    def test_validate_credentials_success(self, mock_get):
        service = WhatsAppService()
        service.access_token = "mock_token"
        service.phone_number_id = "mock_phone_id"
        service.business_account_id = "mock_biz_id"

        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "mock_phone_id" in url:
                resp.status_code = 200
                resp.json.return_value = {"id": "mock_phone_id"}
            elif "message_templates" in url:
                resp.status_code = 200
                name_param = params.get("name") if params else None
                if name_param == service.template_name:
                    resp.json.return_value = {"data": [{"name": service.template_name}]}
                elif name_param == service.pdf_template_name:
                    resp.json.return_value = {"data": [{
                        "name": service.pdf_template_name,
                        "status": "APPROVED",
                        "language": "en",
                        "components": [
                            {"type": "HEADER", "format": "DOCUMENT"},
                            {"type": "BODY", "text": "Hello {{1}} {{2}}"}
                        ]
                    }]}
            return resp

        mock_get.side_effect = side_effect
        
        success, msg = service.validate_credentials()
        
        self.assertTrue(success)
        self.assertIn("✓ API Token: Valid", msg)
        self.assertIn(f"✓ PDF Template: {service.pdf_template_name} exists", msg)
        self.assertIn("✓ BODY Variables (2)", msg)
        self.assertIn("1. 1", msg)
        self.assertIn("2. 2", msg)

    @patch("requests.get")
    def test_validate_credentials_failure(self, mock_get):
        def side_effect(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "HTTP 401: Unauthorized"
            resp.json.return_value = {"error": {"message": "HTTP 401: Unauthorized", "code": 190}}
            return resp

        mock_get.side_effect = side_effect
        
        service = WhatsAppService()
        service.access_token = "invalid_token"
        service.phone_number_id = "invalid_phone_id"
        
        success, msg = service.validate_credentials()
        
        self.assertFalse(success)
        self.assertIn("invalid", msg)

    @patch("requests.post")
    def test_upload_pdf_media_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789"}
        mock_post.return_value = mock_response
        
        service = WhatsAppService()
        service.access_token = "mock_token"
        service.phone_number_id = "mock_phone_id"
        
        # We patch open to mock loading a PDF file
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"%PDF-1.4")):
            with patch("os.path.exists", return_value=True):
                media_id = service.upload_pdf_media("mock_wageslip.pdf")
                
                self.assertEqual(media_id, "123456789")

    @patch("requests.post")
    def test_send_raw_pdf_template_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "wamid.ABC123XYZ"}]
        }
        mock_post.return_value = mock_response

        service = WhatsAppService()
        service.access_token = "mock_token"
        service.phone_number_id = "mock_phone_id"

        result = service.send_raw_pdf_template(
            phone="919876543210",
            template_name="wageslip_pdf",
            media_id="123456789",
            filename="EMP001_January_2026.pdf",
            employee_name="Amit Kumar",
            month_year="January 2026"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["message_id"], "wamid.ABC123XYZ")
        self.assertEqual(result["error"], "")

    def test_build_template_payload_success(self):
        service = WhatsAppService()
        service.template_name = "wageslip"
        
        # Mock a record containing all required 21 fields
        class DummyRecord:
            month_year = "June 2026"
            establishment = "ABC Industries"
            principal_employer = "XYZ Pvt Ltd"
            address = "Noida, UP"
            employee_name = "Amit Kumar"
            workman_id = "EMP001"
            guardian_name = "Ram Kumar"
            designation = "Technical Analyst"
            uan = "UAN12345"
            bank_account = "BANK12345"
            wage_period = "01-06-2026 to 30-06-2026"
            attendance = 26.0
            basic = 15000.0
            da = 1000.0
            allowances = 500.0
            gross_wages = 16500.0
            pf = 1200.0
            esi = 300.0
            other_deductions = 500.0
            net_wages = 14500.0
            issue_date = "29-06-2026"

        record = DummyRecord()
        payload = service.build_template_payload("919876543210", record)
        
        # Verify structure
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["to"], "919876543210")
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "wageslip")
        
        params = payload["template"]["components"][0]["parameters"]
        self.assertEqual(len(params), 21)
        
        # Verify order and formatting fallbacks
        self.assertEqual(params[0]["text"], "June 2026")          # month_year
        self.assertEqual(params[1]["text"], "ABC Industries")       # establishment
        self.assertEqual(params[11]["text"], "26")                 # attendance (float to clean string)
        self.assertEqual(params[12]["text"], "15000")              # basic (float to clean string)
        self.assertEqual(params[15]["text"], "16500")              # gross_wages
        self.assertEqual(params[20]["text"], "29-06-2026")         # issue_date

    def test_build_template_payload_missing_field_fails(self):
        service = WhatsAppService()
        service.template_name = "wageslip"
        
        # Missing standard field (like designation/guardian_name) raises ValueError since silent empty fallbacks are disabled (Requirement 9)
        class DummyRecord:
            month_year = "June 2026"
            establishment = "ABC"
            principal_employer = "XYZ"
            address = "Noida"
            employee_name = "Amit"
            workman_id = "EMP"
            # guardian_name omitted entirely

        record = DummyRecord()
        with self.assertRaises(ValueError):
            service.build_template_payload("919876543210", record)


if __name__ == "__main__":
    unittest.main()
