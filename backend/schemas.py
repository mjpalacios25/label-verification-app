from typing import Literal

from pydantic import BaseModel, Field, field_validator
import re


def _clean_text(value):
    if isinstance(value, str):
        value = value.lower()
        value = re.sub(r'[^a-z0-9\s]', '', value)
        value = value.strip()

    return value


class BeverageInfo(BaseModel):
    brand_name: str = Field(description= "brand name of the spirit, wine, or beer")
    warning_label_text : str = Field(description = "text of the warning label")
    alcohol_content: str = Field(description= "alcoholic volume")
    class_text: str = Field(description="description of the beverage")
    address: str = Field(description="address of the producer of the beverage")

    @field_validator("brand_name", "class_text", "address", mode="before")
    @classmethod
    def clean_text(cls, value):
        return _clean_text(value)


class FormInfo(BaseModel):
    brand_name: str = Field(description= "brand name of the spirit, wine, or beer")
    source: str = Field(description= "denotes whether product is domestic or international")
    type: str = Field(description= "denotes whether product is wine, distilled spirit, or malt beverage")
    alcohol_content: str = Field(description= "alcoholic volume")
    address: str = Field(description="address of the producer of the beverage")

    @field_validator("brand_name", "source", "type", "address", mode="before")
    @classmethod
    def clean_text(cls, value):
        return _clean_text(value)


class DataCheck(BaseModel):
    brand_match: Literal["yes", "no"] = Field(description="yes/no does the brand name match on the PDF and images?")
    warning_match: Literal["yes", "no"] = Field(description="yes/no does the warning label match the requirements")
    alcohol_match: Literal["yes", "no"] = Field(description="yes/no does the alcohol content match on the PDF and images?")
