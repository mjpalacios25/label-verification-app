from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class VerificationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    image_brand_name: str
    image_warning_label_text: str
    image_alcohol_content: str
    image_class_text: str
    image_address: str

    form_brand_name: str
    form_source: str
    form_type: str
    form_alcohol_content: str
    form_address: str

    brand_match: str
    alcohol_match: str
    warning_match: str
