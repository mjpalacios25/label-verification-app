"""
FastAPI route tests for backend/main.py.

Each test uses an in-memory SQLite database injected via dependency override.
LLM calls are mocked so no real network requests are made.
"""

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from backend.main import app
from backend.database import get_session
from backend.models import VerificationRun
from backend.schemas import BeverageInfo, DataCheck, FormInfo
from backend.services.llm_service import _CANONICAL_WARNING


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_engine():
    """Single in-memory SQLite engine shared across the module's tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    """Provide a transactional Session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """TestClient with get_session overridden to use the isolated test DB."""

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fake LLM return values used across multiple tests
# ---------------------------------------------------------------------------


def _make_beverage_info(brand="test spirit") -> BeverageInfo:
    obj = BeverageInfo.__new__(BeverageInfo)
    object.__setattr__(obj, "brand_name", brand)
    object.__setattr__(obj, "warning_label_text", _CANONICAL_WARNING)
    object.__setattr__(obj, "alcohol_content", "40")
    object.__setattr__(obj, "class_text", "distilled spirit")
    object.__setattr__(obj, "address", "123 main st")
    return obj


def _make_form_info(brand="test spirit") -> FormInfo:
    obj = FormInfo.__new__(FormInfo)
    object.__setattr__(obj, "brand_name", brand)
    object.__setattr__(obj, "source", "domestic")
    object.__setattr__(obj, "type", "distilled spirit")
    object.__setattr__(obj, "alcohol_content", "40")
    object.__setattr__(obj, "address", "123 main st")
    return obj


def _make_data_check(
    brand_match="yes", alcohol_match="yes", warning_match="yes"
) -> DataCheck:
    return DataCheck(
        brand_match=brand_match,
        alcohol_match=alcohol_match,
        warning_match=warning_match,
    )


def _image_file(name: str = "front.jpeg", content: bytes = b"fake-jpeg") -> tuple:
    return ("images", (name, io.BytesIO(content), "image/jpeg"))


def _form_file(name: str = "form.pdf", content: bytes = b"fake-pdf") -> tuple:
    return ("form", (name, io.BytesIO(content), "application/pdf"))


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_returns_200(self, client):
        # Arrange — no setup needed

        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200

    def test_returns_status_ok(self, client):
        # Arrange — no setup needed

        # Act
        response = client.get("/health")

        # Assert
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /verify — happy path
# ---------------------------------------------------------------------------


class TestVerifyEndpointSuccess:
    def test_returns_200_with_valid_data_check(self, client):
        # Arrange
        fake_beverage = _make_beverage_info()
        fake_form = _make_form_info()
        fake_check = _make_data_check()

        with (
            patch("backend.main.extract_from_image", return_value=fake_beverage),
            patch("backend.main.extract_structured_data_pdf", return_value=fake_form),
            patch("backend.main.validate_results", return_value=fake_check),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["brand_match"] == "yes"
        assert body["alcohol_match"] == "yes"
        assert body["warning_match"] == "yes"

    def test_response_body_matches_datacheck_schema(self, client):
        # Arrange
        fake_beverage = _make_beverage_info()
        fake_form = _make_form_info()
        fake_check = _make_data_check(brand_match="no", alcohol_match="yes", warning_match="no")

        with (
            patch("backend.main.extract_from_image", return_value=fake_beverage),
            patch("backend.main.extract_structured_data_pdf", return_value=fake_form),
            patch("backend.main.validate_results", return_value=fake_check),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 200
        parsed = DataCheck(**response.json())
        assert parsed.brand_match == "no"
        assert parsed.warning_match == "no"

    def test_saves_verification_run_to_db(self, client, db_session):
        # Arrange
        fake_beverage = _make_beverage_info(brand="my brand")
        fake_form = _make_form_info(brand="my brand")
        fake_check = _make_data_check()

        with (
            patch("backend.main.extract_from_image", return_value=fake_beverage),
            patch("backend.main.extract_structured_data_pdf", return_value=fake_form),
            patch("backend.main.validate_results", return_value=fake_check),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 200
        runs = db_session.exec(select(VerificationRun)).all()
        assert len(runs) == 1
        assert runs[0].image_brand_name == "my brand"
        assert runs[0].brand_match == "yes"

    def test_multiple_images_are_accepted(self, client):
        # Arrange
        fake_beverage = _make_beverage_info()
        fake_form = _make_form_info()
        fake_check = _make_data_check()

        with (
            patch("backend.main.extract_from_image", return_value=fake_beverage),
            patch("backend.main.extract_structured_data_pdf", return_value=fake_form),
            patch("backend.main.validate_results", return_value=fake_check),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[
                    _image_file("front.jpeg"),
                    _image_file("back.jpeg"),
                    _form_file(),
                ],
            )

        # Assert
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /verify — LLM error paths
# ---------------------------------------------------------------------------


class TestVerifyEndpointLlmErrors:
    def test_openai_error_from_extract_image_returns_502(self, client):
        # Arrange
        from openai import OpenAIError

        with patch(
            "backend.main.extract_from_image",
            side_effect=OpenAIError("connection refused"),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 502

    def test_openai_error_from_extract_pdf_returns_502(self, client):
        # Arrange
        from openai import OpenAIError

        fake_beverage = _make_beverage_info()
        with (
            patch("backend.main.extract_from_image", return_value=fake_beverage),
            patch(
                "backend.main.extract_structured_data_pdf",
                side_effect=OpenAIError("timeout"),
            ),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 502

    def test_validation_error_returns_502(self, client):
        # Arrange — simulate the LLM returning malformed JSON that fails Pydantic validation
        from pydantic import ValidationError as PydanticValidationError

        # Build a real ValidationError by attempting an invalid DataCheck
        try:
            DataCheck(brand_match="invalid", warning_match="yes", alcohol_match="yes")
        except PydanticValidationError as exc:
            fake_error = exc

        with patch(
            "backend.main.extract_from_image",
            side_effect=fake_error,
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert response.status_code == 502

    def test_502_detail_message_for_openai_error(self, client):
        # Arrange
        from openai import OpenAIError

        with patch(
            "backend.main.extract_from_image",
            side_effect=OpenAIError("down"),
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert "unavailable" in response.json()["detail"].lower()

    def test_502_detail_message_for_validation_error(self, client):
        # Arrange
        from pydantic import ValidationError as PydanticValidationError

        try:
            DataCheck(brand_match="bad", warning_match="yes", alcohol_match="yes")
        except PydanticValidationError as exc:
            fake_error = exc

        with patch(
            "backend.main.extract_from_image",
            side_effect=fake_error,
        ):
            # Act
            response = client.post(
                "/verify",
                files=[_image_file(), _form_file()],
            )

        # Assert
        assert "malformed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /verify — missing file validation
# ---------------------------------------------------------------------------


class TestVerifyEndpointMissingFiles:
    def test_no_files_returns_422(self, client):
        # Arrange — send no files at all

        # Act
        response = client.post("/verify")

        # Assert
        assert response.status_code in (400, 422)

    def test_no_form_file_returns_422(self, client):
        # Arrange — send images but omit the form field

        # Act
        response = client.post(
            "/verify",
            files=[_image_file()],
        )

        # Assert
        assert response.status_code in (400, 422)

    def test_no_images_returns_422(self, client):
        # Arrange — send form but omit images

        # Act
        response = client.post(
            "/verify",
            files=[_form_file()],
        )

        # Assert
        assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /export
# ---------------------------------------------------------------------------


class TestExportEndpoint:
    def test_returns_200(self, client):
        # Arrange — empty DB is fine for status check

        # Act
        response = client.get("/export")

        # Assert
        assert response.status_code == 200

    def test_content_type_is_text_csv(self, client):
        # Arrange — no data needed to verify headers

        # Act
        response = client.get("/export")

        # Assert
        assert "text/csv" in response.headers["content-type"]

    def test_content_disposition_attachment_filename(self, client):
        # Arrange

        # Act
        response = client.get("/export")

        # Assert
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "verification_runs.csv" in disposition

    def test_csv_includes_header_row(self, client):
        # Arrange — expected headers match VerificationRun fields used in export

        # Act
        response = client.get("/export")
        lines = response.text.strip().splitlines()

        # Assert
        assert len(lines) >= 1
        header = lines[0]
        for expected_col in [
            "id",
            "created_at",
            "image_brand_name",
            "image_warning_label_text",
            "image_alcohol_content",
            "image_class_text",
            "image_address",
            "form_brand_name",
            "form_source",
            "form_type",
            "form_alcohol_content",
            "form_address",
            "brand_match",
            "alcohol_match",
            "warning_match",
        ]:
            assert expected_col in header, f"Expected column '{expected_col}' missing from CSV header"

    def test_csv_contains_one_data_row_after_verification(self, client, db_session):
        # Arrange — write a VerificationRun directly into the test DB
        run = VerificationRun(
            image_brand_name="export brand",
            image_warning_label_text=_CANONICAL_WARNING,
            image_alcohol_content="40",
            image_class_text="distilled spirit",
            image_address="123 main st",
            form_brand_name="export brand",
            form_source="domestic",
            form_type="distilled spirit",
            form_alcohol_content="40",
            form_address="123 main st",
            brand_match="yes",
            alcohol_match="yes",
            warning_match="yes",
        )
        db_session.add(run)
        db_session.commit()

        # Act
        response = client.get("/export")
        lines = response.text.strip().splitlines()

        # Assert — header + at least one data row
        assert len(lines) >= 2, "Expected header row plus at least one data row"
        assert "export brand" in lines[1]

    def test_csv_data_row_contains_match_results(self, client, db_session):
        # Arrange
        run = VerificationRun(
            image_brand_name="match brand",
            image_warning_label_text=_CANONICAL_WARNING,
            image_alcohol_content="45",
            image_class_text="whiskey",
            image_address="456 bourbon st",
            form_brand_name="match brand",
            form_source="domestic",
            form_type="distilled spirit",
            form_alcohol_content="45",
            form_address="456 bourbon st",
            brand_match="yes",
            alcohol_match="no",
            warning_match="yes",
        )
        db_session.add(run)
        db_session.commit()

        # Act
        response = client.get("/export")
        lines = response.text.strip().splitlines()

        # Assert
        data_row = lines[1]
        assert "yes" in data_row
        assert "no" in data_row
