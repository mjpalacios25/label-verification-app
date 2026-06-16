"""
Unit tests for backend/database.py.

Uses an in-memory SQLite engine to avoid touching the real label_verification.db.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine, inspect, text

from backend.models import VerificationRun  # noqa: F401 — registers table metadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def in_memory_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# create_db_and_tables
# ---------------------------------------------------------------------------


class TestCreateDbAndTables:
    def test_verificationrun_table_is_created(self, in_memory_engine):
        # Arrange
        # We call SQLModel.metadata.create_all directly (same as create_db_and_tables)
        # to keep the test fully isolated from the module-level engine.

        # Act
        SQLModel.metadata.create_all(in_memory_engine)

        # Assert
        inspector = inspect(in_memory_engine)
        assert "verificationrun" in inspector.get_table_names()

    def test_verificationrun_table_has_id_column(self, in_memory_engine):
        # Arrange
        SQLModel.metadata.create_all(in_memory_engine)

        # Act
        inspector = inspect(in_memory_engine)
        columns = {col["name"] for col in inspector.get_columns("verificationrun")}

        # Assert
        assert "id" in columns

    def test_verificationrun_table_has_all_expected_columns(self, in_memory_engine):
        # Arrange
        SQLModel.metadata.create_all(in_memory_engine)
        expected_columns = {
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
        }

        # Act
        inspector = inspect(in_memory_engine)
        actual_columns = {col["name"] for col in inspector.get_columns("verificationrun")}

        # Assert
        assert expected_columns == actual_columns

    def test_create_db_and_tables_is_idempotent(self, in_memory_engine):
        # Arrange — calling create_all twice must not raise
        SQLModel.metadata.create_all(in_memory_engine)

        # Act & Assert
        SQLModel.metadata.create_all(in_memory_engine)  # second call must not raise

        inspector = inspect(in_memory_engine)
        assert "verificationrun" in inspector.get_table_names()


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_get_session_yields_a_session(self, in_memory_engine):
        # Arrange
        SQLModel.metadata.create_all(in_memory_engine)

        # Act
        gen = Session(in_memory_engine)

        # Assert — the context manager gives a usable Session
        with gen as session:
            assert isinstance(session, Session)

    def test_session_can_execute_query(self, in_memory_engine):
        # Arrange
        SQLModel.metadata.create_all(in_memory_engine)

        # Act
        with Session(in_memory_engine) as session:
            result = session.exec(text("SELECT 1")).one()

        # Assert
        assert result == (1,) or result[0] == 1

    def test_session_supports_queries_within_context(self, in_memory_engine):
        # Arrange
        SQLModel.metadata.create_all(in_memory_engine)

        # Act & Assert — the session must successfully execute a query inside its context
        with Session(in_memory_engine) as session:
            result = session.exec(text("SELECT 1")).one()
            assert result[0] == 1

    def test_real_get_session_generator_yields_session_then_stops(self):
        """
        Exercise the actual get_session generator using its own in-memory engine
        via module-level engine replacement — verify it yields exactly one Session
        and then the generator is fully exhausted.
        """
        # Arrange
        from sqlmodel import Session as SQLModelSession
        from backend import database as db_module

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(test_engine)

        original_engine = db_module.engine
        db_module.engine = test_engine

        try:
            # Act
            gen = db_module.get_session()
            session = next(gen)

            # Assert — the yielded value must be a Session
            assert isinstance(session, SQLModelSession)

            # The generator must be exhausted after exactly one value
            with pytest.raises(StopIteration):
                next(gen)
        finally:
            db_module.engine = original_engine
            test_engine.dispose()
