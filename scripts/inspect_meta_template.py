"""Utility script to query the Meta Graph API for template definitions and print metadata."""

import os
import sys
import json
import requests

# Add the project root to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import get_session
from database.models import Setting


def main():
    session = get_session()
    settings = {s.key: s.value for s in session.query(Setting).all()}
    session.close()

    access_token = settings.get("ACCESS_TOKEN", "")
    phone_id = settings.get("PHONE_NUMBER_ID", "")
    biz_id = settings.get("BUSINESS_ACCOUNT_ID", "")
    api_version = settings.get("API_VERSION", "v25.0")
    template_name = settings.get("TEMPLATE_NAME", "wageslip")
    template_lang = settings.get("TEMPLATE_LANGUAGE", "en")

    print("=== Step 1: Active Configuration ===")
    print(f"Template Name: {template_name}")
    print(f"Language:      {template_lang}")
    print(f"Phone ID:      {phone_id}")
    print(f"Business ID:   {biz_id}")
    print(f"API Version:   {api_version}")
    print(f"Has Token:     {bool(access_token)}")
    print("-" * 50)

    if not access_token or not biz_id:
        print("Error: ACCESS_TOKEN or BUSINESS_ACCOUNT_ID is missing from settings DB.")
        return

    # Call GET /vXX.X/<BUSINESS_ACCOUNT_ID>/message_templates
    url = f"https://graph.facebook.com/{api_version}/{biz_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "name": template_name
    }

    print("=== Step 2: Fetching Live Template from Meta ===")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        print(f"HTTP Response Code: {response.status_code}")
        
        if response.status_code != 200:
            print("Failed to fetch templates. Response text:")
            print(response.text)
            return

        data = response.json()
        print("Full Meta Templates JSON Response:")
        print(json.dumps(data, indent=2))
        print("-" * 50)
        
        # Verify definitions
        templates = data.get("data", [])
        if not templates:
            print(f"No templates found matching name '{template_name}' under Business ID '{biz_id}'.")
            return

        for t in templates:
            print(f"Template: {t.get('name')} | Status: {t.get('status')} | Category: {t.get('category')}")
            for comp in t.get("components", []):
                comp_type = comp.get("type")
                print(f"Component Type: {comp_type}")
                if "text" in comp:
                    print(f"Text Content:\n{comp['text']}")
                if "format" in comp:
                    print(f"Format: {comp['format']}")
                if "example" in comp:
                    print(f"Examples: {json.dumps(comp['example'], indent=2)}")
                print()

    except Exception as e:
        print(f"Exception during request: {e}")


if __name__ == "__main__":
    main()
