"""
Unit tests for backend/schemas.py.

All tests are pure — no I/O, no mocking required.
"""

import pytest
from pydantic import ValidationError

from backend.schemas import BeverageInfo, DataCheck, FormInfo


# ---------------------------------------------------------------------------
# BeverageInfo
# ---------------------------------------------------------------------------


class TestBeverageInfoCleanText:
    """clean_text validator on BeverageInfo applies to brand_name, class_text, address."""

    def test_brand_name_is_lowercased(self):
        # Arrange
        raw = "JACK DANIELS"

        # Act
        result = BeverageInfo(
            brand_name=raw,
            warning_label_text="Government Warning: ...",
            alcohol_content="40",
            class_text="Tennessee Whiskey",
            address="Lynchburg, TN",
        )

        # Assert
        assert result.brand_name == "jack daniels"

    def test_brand_name_strips_punctuation(self):
        # Arrange
        raw = "Jack Daniel's Old No. 7"

        # Act
        result = BeverageInfo(
            brand_name=raw,
            warning_label_text="Government Warning: ...",
            alcohol_content="40",
            class_text="tennessee whiskey",
            address="lynchburg tn",
        )

        # Assert
        # apostrophe, period should be removed; letters/digits/spaces survive
        assert "'" not in result.brand_name
        assert "." not in result.brand_name
        assert result.brand_name == "jack daniels old no 7"

    def test_class_text_is_lowercased_and_stripped(self):
        # Arrange
        raw = "  Tennessee Whiskey!  "

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text="Government Warning: ...",
            alcohol_content="40",
            class_text=raw,
            address="test address",
        )

        # Assert
        assert result.class_text == "tennessee whiskey"

    def test_address_is_lowercased_and_stripped(self):
        # Arrange
        raw = "  1 DISTILLERY LANE, LYNCHBURG, TN 37352  "

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text="Government Warning: ...",
            alcohol_content="40",
            class_text="whiskey",
            address=raw,
        )

        # Assert
        assert result.address == "1 distillery lane lynchburg tn 37352"

    def test_warning_label_text_preserves_case(self):
        # Arrange — warning text must NOT be lowercased (not in validator list)
        raw = "GOVERNMENT WARNING: (1) According to the Surgeon General"

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text=raw,
            alcohol_content="40",
            class_text="whiskey",
            address="test address",
        )

        # Assert
        assert result.warning_label_text == raw

    def test_warning_label_text_preserves_punctuation(self):
        # Arrange — colons, parentheses, commas must survive
        raw = "GOVERNMENT WARNING: (1) risk of birth defects. (2) impairs ability."

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text=raw,
            alcohol_content="40",
            class_text="whiskey",
            address="test address",
        )

        # Assert
        assert ":" in result.warning_label_text
        assert "(" in result.warning_label_text
        assert ")" in result.warning_label_text
        assert "." in result.warning_label_text

    def test_alcohol_content_preserves_decimal_point(self):
        # Arrange — "45.5" must survive unchanged (not in validator list)
        raw = "45.5"

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text="Government Warning: ...",
            alcohol_content=raw,
            class_text="whiskey",
            address="test address",
        )

        # Assert
        assert result.alcohol_content == "45.5"

    def test_alcohol_content_preserves_integer_string(self):
        # Arrange
        raw = "40"

        # Act
        result = BeverageInfo(
            brand_name="test brand",
            warning_label_text="Government Warning: ...",
            alcohol_content=raw,
            class_text="whiskey",
            address="test address",
        )

        # Assert
        assert result.alcohol_content == "40"

    def test_valid_instantiation_with_all_fields(self):
        # Arrange
        data = {
            "brand_name": "Black Label",
            "warning_label_text": (
                "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
                "drink alcoholic beverages during pregnancy because of the risk of birth defects."
                "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
                "operate machinery, and may cause health problems."
            ),
            "alcohol_content": "40",
            "class_text": "Blended Scotch Whisky",
            "address": "Edinburgh, Scotland",
        }

        # Act
        result = BeverageInfo(**data)

        # Assert
        assert isinstance(result, BeverageInfo)
        assert result.brand_name == "black label"
        assert result.class_text == "blended scotch whisky"
        assert result.address == "edinburgh scotland"
        # warning and alcohol_content are untouched
        assert result.warning_label_text == data["warning_label_text"]
        assert result.alcohol_content == "40"


# ---------------------------------------------------------------------------
# FormInfo
# ---------------------------------------------------------------------------


class TestFormInfoCleanText:
    """clean_text validator on FormInfo applies to brand_name, source, type, address."""

    def test_brand_name_is_lowercased(self):
        # Arrange
        raw = "CORONA EXTRA"

        # Act
        result = FormInfo(
            brand_name=raw,
            source="domestic",
            type="malt beverage",
            alcohol_content="4.6",
            address="San Antonio, TX",
        )

        # Assert
        assert result.brand_name == "corona extra"

    def test_source_is_lowercased_and_stripped(self):
        # Arrange
        raw = "  DOMESTIC  "

        # Act
        result = FormInfo(
            brand_name="corona extra",
            source=raw,
            type="malt beverage",
            alcohol_content="4.6",
            address="san antonio tx",
        )

        # Assert
        assert result.source == "domestic"

    def test_type_strips_punctuation(self):
        # Arrange
        raw = "Malt Beverage (Beer)"

        # Act
        result = FormInfo(
            brand_name="test brand",
            source="domestic",
            type=raw,
            alcohol_content="5.0",
            address="test address",
        )

        # Assert
        assert "(" not in result.type
        assert ")" not in result.type
        assert result.type == "malt beverage beer"

    def test_address_is_lowercased_and_punctuation_removed(self):
        # Arrange
        raw = "123 Brewery Rd., San Antonio, TX 78201"

        # Act
        result = FormInfo(
            brand_name="test brand",
            source="domestic",
            type="malt beverage",
            alcohol_content="5.0",
            address=raw,
        )

        # Assert
        assert result.address == "123 brewery rd san antonio tx 78201"

    def test_alcohol_content_preserves_decimal_point(self):
        # Arrange
        raw = "4.6"

        # Act
        result = FormInfo(
            brand_name="test brand",
            source="domestic",
            type="malt beverage",
            alcohol_content=raw,
            address="test address",
        )

        # Assert
        assert result.alcohol_content == "4.6"

    def test_alcohol_content_preserves_integer_string(self):
        # Arrange
        raw = "40"

        # Act
        result = FormInfo(
            brand_name="test brand",
            source="domestic",
            type="distilled spirit",
            alcohol_content=raw,
            address="test address",
        )

        # Assert
        assert result.alcohol_content == "40"

    def test_valid_instantiation_with_all_fields(self):
        # Arrange
        data = {
            "brand_name": "Test Spirit",
            "source": "Domestic",
            "type": "Distilled Spirit",
            "alcohol_content": "40.0",
            "address": "123 Main St, Louisville, KY",
        }

        # Act
        result = FormInfo(**data)

        # Assert
        assert isinstance(result, FormInfo)
        assert result.brand_name == "test spirit"
        assert result.source == "domestic"
        assert result.type == "distilled spirit"
        assert result.alcohol_content == "40.0"
        assert result.address == "123 main st louisville ky"


# ---------------------------------------------------------------------------
# DataCheck
# ---------------------------------------------------------------------------


class TestDataCheck:
    """DataCheck accepts only Literal["yes", "no"] for all three match fields."""

    @pytest.mark.parametrize(
        "brand_match,warning_match,alcohol_match",
        [
            ("yes", "yes", "yes"),
            ("no", "no", "no"),
            ("yes", "no", "yes"),
            ("no", "yes", "no"),
        ],
    )
    def test_valid_yes_no_combinations(self, brand_match, warning_match, alcohol_match):
        # Arrange — parametrize handles setup

        # Act
        result = DataCheck(
            brand_match=brand_match,
            warning_match=warning_match,
            alcohol_match=alcohol_match,
        )

        # Assert
        assert result.brand_match == brand_match
        assert result.warning_match == warning_match
        assert result.alcohol_match == alcohol_match

    @pytest.mark.parametrize("invalid_value", ["true", "True", "Yes", "No", "maybe", "1", "0", ""])
    def test_brand_match_rejects_invalid_literal(self, invalid_value):
        # Arrange
        invalid_input = {
            "brand_match": invalid_value,
            "warning_match": "yes",
            "alcohol_match": "yes",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            DataCheck(**invalid_input)

    @pytest.mark.parametrize("invalid_value", ["true", "True", "Yes", "No", "maybe", "1", "0", ""])
    def test_warning_match_rejects_invalid_literal(self, invalid_value):
        # Arrange
        invalid_input = {
            "brand_match": "yes",
            "warning_match": invalid_value,
            "alcohol_match": "yes",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            DataCheck(**invalid_input)

    @pytest.mark.parametrize("invalid_value", ["true", "True", "Yes", "No", "maybe", "1", "0", ""])
    def test_alcohol_match_rejects_invalid_literal(self, invalid_value):
        # Arrange
        invalid_input = {
            "brand_match": "yes",
            "warning_match": "yes",
            "alcohol_match": invalid_value,
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            DataCheck(**invalid_input)

    def test_all_fields_required(self):
        # Arrange — omit all fields

        # Act & Assert
        with pytest.raises(ValidationError):
            DataCheck()
