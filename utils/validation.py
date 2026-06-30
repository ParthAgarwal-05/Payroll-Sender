"""Validation utilities for template mappings in the Payroll WhatsApp System."""

import re
from typing import Optional

_KEY_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_CONTROL_CHAR_PATTERN: re.Pattern[str] = re.compile(r"[\x00-\x1f\x7f]")
_MAX_VALUE_LENGTH: int = 128


def validate_mapping_key(key: str) -> tuple[bool, str]:
    """Validate a single mapping key."""
    if not key:
        return False, "Mapping key must not be empty"

    if not _KEY_PATTERN.match(key):
        return (
            False,
            f"Mapping key '{key}' is invalid. Keys must start with a letter "
            f"or underscore, contain only alphanumeric characters or "
            f"underscores, and be at most 64 characters long.",
        )

    return True, ""


def validate_mapping_value(value: str) -> tuple[bool, str]:
    """Validate a single mapping value (column name reference)."""
    if not value or not value.strip():
        return False, "Mapping value must not be empty"

    if len(value) > _MAX_VALUE_LENGTH:
        return (
            False,
            f"Mapping value is too long ({len(value)} chars). "
            f"Maximum allowed length is {_MAX_VALUE_LENGTH} characters.",
        )

    if _CONTROL_CHAR_PATTERN.search(value):
        return False, "Mapping value must not contain control characters"

    return True, ""


def validate_template_mapping(mapping: dict) -> tuple[bool, str]:
    """Validate an entire template parameter mapping."""
    if not mapping:
        return False, "Template mapping must not be empty"

    for key, value in mapping.items():
        key_valid, key_error = validate_mapping_key(str(key))
        if not key_valid:
            return False, key_error

        value_valid, value_error = validate_mapping_value(str(value))
        if not value_valid:
            return False, f"Invalid value for key '{key}': {value_error}"

    return True, ""


def extract_template_parameters(
    mapping: dict,
    row_data: dict,
) -> tuple[list[dict[str, str]], list[str]]:
    """Extract template parameters from row data, using a case-insensitive mapping."""
    parameters: list[dict[str, str]] = []
    missing: list[str] = []

    # Case-insensitive column search
    data_columns_lower: dict[str, any] = {
        str(k).lower(): v for k, v in row_data.items()
    }

    for param_key, column_name in mapping.items():
        col_lower = str(column_name).lower()
        if col_lower not in data_columns_lower:
            missing.append(str(column_name))
            continue
            
        value = data_columns_lower[col_lower]
        if value is None or str(value).strip() == "":
            missing.append(str(column_name))
            continue
            
        parameters.append({
            "type": "text",
            "text": str(value).strip()
        })

    return parameters, missing


def validate_mapping_against_data(
    mapping: dict,
    sample_row: dict,
) -> tuple[bool, list[str]]:
    """Check that every mapped column exists in the data and is not empty."""
    _, missing = extract_template_parameters(mapping, sample_row)
    return len(missing) == 0, missing


def validate_parameter_count(
    mapping: dict,
    expected_count: Optional[int] = None,
) -> tuple[bool, str]:
    """Validate that the mapping has the expected number of parameters."""
    if expected_count is None:
        return True, ""

    actual = len(mapping)
    if actual != expected_count:
        return (
            False,
            f"Template expects {expected_count} parameter(s) but mapping "
            f"contains {actual}.",
        )

    return True, ""
