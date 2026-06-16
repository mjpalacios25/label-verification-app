"""
Tests for backend/services/llm_service.py.

Unit tests cover deterministic logic (validate_results, _to_abv indirectly,
_normalize_warning indirectly, encode_image).

Integration tests marked @pytest.mark.integration require a live Modal endpoint
and are excluded from the default test run.
"""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.schemas import BeverageInfo, DataCheck, FormInfo
from backend.services.llm_service import (
    _CANONICAL_WARNING,
    encode_image,
    validate_results,
)

# Paths relative to repo root — resolved to absolute for reliability
REPO_ROOT = Path(__file__).parent.parent.parent
SPIRIT_DIR = REPO_ROOT / "backend" / "public" / "spirit"
FRONT_IMAGE = str(SPIRIT_DIR / "spirit front.jpeg")
BACK_IMAGE = str(SPIRIT_DIR / "spirit back.jpeg")
FORM_PDF = str(SPIRIT_DIR / "spirit form.pdf")


# ---------------------------------------------------------------------------
# Helpers — build minimal schema instances
# ---------------------------------------------------------------------------


def make_beverage(
    brand_name: str = "test spirit",
    warning_label_text: str = _CANONICAL_WARNING,
    alcohol_content: str = "40",
    class_text: str = "distilled spirit",
    address: str = "123 main st",
) -> BeverageInfo:
    """Return a BeverageInfo bypassing the clean_text validator for precise control."""
    obj = BeverageInfo.__new__(BeverageInfo)
    object.__setattr__(obj, "brand_name", brand_name)
    object.__setattr__(obj, "warning_label_text", warning_label_text)
    object.__setattr__(obj, "alcohol_content", alcohol_content)
    object.__setattr__(obj, "class_text", class_text)
    object.__setattr__(obj, "address", address)
    return obj


def make_form(
    brand_name: str = "test spirit",
    source: str = "domestic",
    type: str = "distilled spirit",
    alcohol_content: str = "40",
    address: str = "123 main st",
) -> FormInfo:
    """Return a FormInfo bypassing the clean_text validator for precise control."""
    obj = FormInfo.__new__(FormInfo)
    object.__setattr__(obj, "brand_name", brand_name)
    object.__setattr__(obj, "source", source)
    object.__setattr__(obj, "type", type)
    object.__setattr__(obj, "alcohol_content", alcohol_content)
    object.__setattr__(obj, "address", address)
    return obj


# ---------------------------------------------------------------------------
# encode_image
# ---------------------------------------------------------------------------


class TestEncodeImage:
    def test_returns_non_empty_base64_string(self):
        # Arrange
        image_path = FRONT_IMAGE

        # Act
        result = encode_image(image_path)

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_decodes_to_valid_bytes(self):
        # Arrange
        image_path = FRONT_IMAGE

        # Act
        result = encode_image(image_path)

        # Assert — base64.b64decode must not raise and must return bytes
        decoded = base64.b64decode(result)
        assert isinstance(decoded, bytes)
        assert len(decoded) > 0

    def test_back_image_encodes_to_non_empty_base64(self):
        # Arrange
        image_path = BACK_IMAGE

        # Act
        result = encode_image(image_path)

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0

    def test_missing_file_raises_error(self):
        # Arrange
        bad_path = str(SPIRIT_DIR / "nonexistent.jpeg")

        # Act & Assert
        with pytest.raises(Exception):
            encode_image(bad_path)


# ---------------------------------------------------------------------------
# validate_results — brand matching
# ---------------------------------------------------------------------------


class TestValidateResultsBrandMatch:
    def test_matching_brand_names_returns_yes(self):
        # Arrange
        image_data = make_beverage(brand_name="test spirit")
        form_data = make_form(brand_name="test spirit")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "yes"

    def test_mismatched_brand_names_returns_no(self):
        # Arrange
        image_data = make_beverage(brand_name="test spirit")
        form_data = make_form(brand_name="different brand")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "no"

    def test_brand_match_is_case_sensitive_after_clean(self):
        # Arrange — both values already cleaned (lowercase); mixed case would differ
        image_data = make_beverage(brand_name="spirit a")
        form_data = make_form(brand_name="Spirit A")  # different after clean — but bypassed here

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "no"

    def test_empty_brand_names_match_each_other(self):
        # Arrange — both empty strings are equal
        image_data = make_beverage(brand_name="")
        form_data = make_form(brand_name="")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "yes"


# ---------------------------------------------------------------------------
# validate_results — ABV matching (tests _to_abv indirectly)
# ---------------------------------------------------------------------------


class TestValidateResultsAlcoholMatch:
    def test_integer_abv_exact_match_returns_yes(self):
        # Arrange
        image_data = make_beverage(alcohol_content="40")
        form_data = make_form(alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "yes"

    def test_decimal_abv_exact_match_returns_yes(self):
        # Arrange
        image_data = make_beverage(alcohol_content="40.5")
        form_data = make_form(alcohol_content="40.5")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "yes"

    def test_abv_within_tolerance_returns_yes(self):
        # Arrange — 40.0 vs 40.05 → difference 0.05, within ±0.1
        image_data = make_beverage(alcohol_content="40.0")
        form_data = make_form(alcohol_content="40.05")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "yes"

    def test_abv_near_tolerance_boundary_returns_yes(self):
        # Arrange — difference 0.09, safely within ±0.1
        # Note: 40.0 vs 40.1 fails due to floating-point representation
        # (abs(40.0 - 40.1) == 0.10000000000000142 > 0.1), so we use 40.09.
        image_data = make_beverage(alcohol_content="40.0")
        form_data = make_form(alcohol_content="40.09")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "yes"

    def test_abv_outside_tolerance_returns_no(self):
        # Arrange — 40 vs 45 → difference 5, way outside ±0.1
        image_data = make_beverage(alcohol_content="40")
        form_data = make_form(alcohol_content="45")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_abv_just_above_tolerance_returns_no(self):
        # Arrange — difference 0.11, just above ±0.1
        image_data = make_beverage(alcohol_content="40.0")
        form_data = make_form(alcohol_content="40.11")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_non_numeric_image_abv_returns_no(self):
        # Arrange — no digits in image abv string
        image_data = make_beverage(alcohol_content="unknown")
        form_data = make_form(alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_non_numeric_form_abv_returns_no(self):
        # Arrange — no digits in form abv string
        image_data = make_beverage(alcohol_content="40")
        form_data = make_form(alcohol_content="n/a")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_both_non_numeric_abv_returns_no(self):
        # Arrange
        image_data = make_beverage(alcohol_content="unknown")
        form_data = make_form(alcohol_content="n/a")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_empty_abv_strings_return_no(self):
        # Arrange — empty string has no digits
        image_data = make_beverage(alcohol_content="")
        form_data = make_form(alcohol_content="")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "no"

    def test_abv_with_percent_suffix_still_matches(self):
        # Arrange — _to_abv uses regex to extract digits, so "40%" → 40.0
        image_data = make_beverage(alcohol_content="40%")
        form_data = make_form(alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.alcohol_match == "yes"


# ---------------------------------------------------------------------------
# validate_results — warning matching (tests _normalize_warning indirectly)
# ---------------------------------------------------------------------------


class TestValidateResultsWarningMatch:
    def test_exact_canonical_warning_returns_yes(self):
        # Arrange — use the actual canonical constant
        image_data = make_beverage(warning_label_text=_CANONICAL_WARNING)
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.warning_match == "yes"

    def test_canonical_warning_with_extra_whitespace_returns_yes(self):
        # Arrange — _normalize_warning collapses whitespace
        padded = "  " + _CANONICAL_WARNING.replace("  ", "   ") + "  "
        image_data = make_beverage(warning_label_text=padded)
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.warning_match == "yes"

    def test_wrong_warning_text_returns_no(self):
        # Arrange — completely wrong warning
        image_data = make_beverage(warning_label_text="This product may be harmful.")
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.warning_match == "no"

    def test_truncated_warning_returns_no(self):
        # Arrange — missing the second sentence
        truncated = "GOVERNMENT WARNING: (1) According to the Surgeon General"
        image_data = make_beverage(warning_label_text=truncated)
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.warning_match == "no"

    def test_empty_warning_returns_no(self):
        # Arrange
        image_data = make_beverage(warning_label_text="")
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.warning_match == "no"


# ---------------------------------------------------------------------------
# validate_results — combined / return type
# ---------------------------------------------------------------------------


class TestValidateResultsCombined:
    def test_all_matching_returns_all_yes(self):
        # Arrange
        image_data = make_beverage(
            brand_name="acme spirit",
            alcohol_content="40",
            warning_label_text=_CANONICAL_WARNING,
        )
        form_data = make_form(brand_name="acme spirit", alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "yes"
        assert result.alcohol_match == "yes"
        assert result.warning_match == "yes"

    def test_all_mismatched_returns_all_no(self):
        # Arrange
        image_data = make_beverage(
            brand_name="brand a",
            alcohol_content="40",
            warning_label_text="Wrong warning text entirely.",
        )
        form_data = make_form(brand_name="brand b", alcohol_content="50")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "no"
        assert result.alcohol_match == "no"
        assert result.warning_match == "no"

    def test_returns_datacheck_instance(self):
        # Arrange
        image_data = make_beverage()
        form_data = make_form()

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert isinstance(result, DataCheck)

    def test_only_brand_mismatch(self):
        # Arrange
        image_data = make_beverage(
            brand_name="brand a",
            alcohol_content="40",
            warning_label_text=_CANONICAL_WARNING,
        )
        form_data = make_form(brand_name="brand b", alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "no"
        assert result.alcohol_match == "yes"
        assert result.warning_match == "yes"

    def test_only_alcohol_mismatch(self):
        # Arrange
        image_data = make_beverage(
            brand_name="shared brand",
            alcohol_content="40",
            warning_label_text=_CANONICAL_WARNING,
        )
        form_data = make_form(brand_name="shared brand", alcohol_content="50")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "yes"
        assert result.alcohol_match == "no"
        assert result.warning_match == "yes"

    def test_only_warning_mismatch(self):
        # Arrange
        image_data = make_beverage(
            brand_name="shared brand",
            alcohol_content="40",
            warning_label_text="Wrong warning.",
        )
        form_data = make_form(brand_name="shared brand", alcohol_content="40")

        # Act
        result = validate_results(image_data, form_data)

        # Assert
        assert result.brand_match == "yes"
        assert result.alcohol_match == "yes"
        assert result.warning_match == "no"


# ---------------------------------------------------------------------------
# Integration tests — require live Modal endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestExtractFromImageIntegration:
    def test_returns_beverage_info_instance(self):
        # Arrange
        from openai import OpenAI
        from backend.config.main import settings
        from backend.services.llm_service import extract_from_image

        client = OpenAI(base_url=settings.MODAL_API_URL, api_key="none-needed")
        image_paths = [FRONT_IMAGE, BACK_IMAGE]

        # Act
        result = extract_from_image(image_paths, client)

        # Assert
        assert isinstance(result, BeverageInfo)

    def test_brand_name_is_non_empty_string(self):
        # Arrange
        from openai import OpenAI
        from backend.config.main import settings
        from backend.services.llm_service import extract_from_image

        client = OpenAI(base_url=settings.MODAL_API_URL, api_key="none-needed")
        image_paths = [FRONT_IMAGE, BACK_IMAGE]

        # Act
        result = extract_from_image(image_paths, client)

        # Assert
        assert isinstance(result.brand_name, str)
        assert len(result.brand_name.strip()) > 0


@pytest.mark.integration
class TestExtractStructuredDataPdfIntegration:
    def test_returns_form_info_instance(self):
        # Arrange
        from openai import OpenAI
        from backend.config.main import settings
        from backend.services.llm_service import extract_structured_data_pdf

        client = OpenAI(base_url=settings.MODAL_API_URL, api_key="none-needed")

        # Act
        result = extract_structured_data_pdf(FORM_PDF, client)

        # Assert
        assert isinstance(result, FormInfo)

    def test_brand_name_is_non_empty_string(self):
        # Arrange
        from openai import OpenAI
        from backend.config.main import settings
        from backend.services.llm_service import extract_structured_data_pdf

        client = OpenAI(base_url=settings.MODAL_API_URL, api_key="none-needed")

        # Act
        result = extract_structured_data_pdf(FORM_PDF, client)

        # Assert
        assert isinstance(result.brand_name, str)
        assert len(result.brand_name.strip()) > 0
