import json
import base64
import io
import re as _re
from pathlib import Path

from PIL import Image
import pymupdf
from openai import OpenAI, OpenAIError
from rapidfuzz import fuzz

from ..config.main import settings
from ..schemas import BeverageInfo, FormInfo, DataCheck


def encode_image(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_from_image(image_paths: list, client: OpenAI) -> BeverageInfo:
    schema = BeverageInfo.model_json_schema()

    content = []
    for image in image_paths:
        image_data = encode_image(image)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
        })

    prompt = """
    Extract the following structured data from the label images above:

    - brand_name (str): brand name that is typically prominently displayed on the label
    - warning_label_text (str): text that begins with "government warning"
    - alcohol_content (str): displayed as a percentage (e.g. 45% alc/vol). return only the number.
    - class_text (str): description of the beverage (e.g. Ale with honey, Rum with natural flavors, Chardonnay)
    - address (str): address of the producer of the beverage

    Return as structured JSON with the exact keys above.
    """

    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    response = client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "BeverageInfo",
                "strict": True,
                "schema": schema
            }
        }
    )

    if not response.choices or response.choices[0].message.content is None:
        raise OpenAIError("LLM returned an empty response")
    return BeverageInfo.model_validate_json(response.choices[0].message.content)


def extract_from_pdf(pdf_path: str) -> str:
    pdf = pymupdf.open(pdf_path)
    return pdf[0].get_text()


def extract_structured_data_pdf(pdf_path: str, client: OpenAI) -> FormInfo:
    schema = FormInfo.model_json_schema()
    text = extract_from_pdf(pdf_path)

    prompt = f"""Extract the following structured data from the text below:

    - brand_name (str): brand name listed in the brand name field of the form
    - source (str): whether this is a domestic or international product as noted by the check mark in the source of product field
    - type (str): whether product is a wine, distilled spirit, or malt beverage as noted by the check mark in the type of product field
    - alcohol_content (str): displayed as a percentage (e.g. 45% alc/vol) in the formula field of the form. return only the number.
    - address (str): address of the producer of the beverage

    Return as structured JSON with the exact keys above.

    Text:
    {text}
    """

    messages = [{"role": "user", "content": prompt}]

    response = client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "FormInfo",
                "strict": True,
                "schema": schema
            }
        }
    )

    if not response.choices or response.choices[0].message.content is None:
        raise OpenAIError("LLM returned an empty response")
    return FormInfo.model_validate_json(response.choices[0].message.content)


_CANONICAL_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects."
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)


_WARNING_SIMILARITY_THRESHOLD = 90


def _normalize_warning(text: str) -> str:
    return _re.sub(r"\s+", " ", text.lower().strip())


def _to_abv(value: str) -> float | None:
    m = _re.search(r"\d+(?:\.\d+)?", value or "")
    return float(m.group()) if m else None


def validate_results(image_results: BeverageInfo, pdf_results: FormInfo) -> DataCheck:
    brand_match = image_results.brand_name == pdf_results.brand_name

    image_abv = _to_abv(image_results.alcohol_content)
    form_abv = _to_abv(pdf_results.alcohol_content)
    alcohol_match = (
        image_abv is not None
        and form_abv is not None
        and abs(image_abv - form_abv) <= 0.1
    )

    warning_match = (
        fuzz.ratio(
            _normalize_warning(image_results.warning_label_text),
            _normalize_warning(_CANONICAL_WARNING),
        )
        >= _WARNING_SIMILARITY_THRESHOLD
    )

    return DataCheck(
        brand_match="yes" if brand_match else "no",
        alcohol_match="yes" if alcohol_match else "no",
        warning_match="yes" if warning_match else "no",
    )


def main():
    client = OpenAI(
        base_url="http://localhost:8080/v1",
        api_key="none-needed",
    )

    public = Path(__file__).parent.parent / "public"
    images = list(public.rglob("*.jpeg"))
    forms = list(public.rglob("*.pdf"))

    pdf_result = extract_structured_data_pdf(forms[0], client)
    print("pdf result:", pdf_result.model_dump_json())

    image_result = extract_from_image(images, client)
    print("image result:", image_result.model_dump_json())

    check_result = validate_results(image_result, pdf_result)
    print("check result:", check_result)


if __name__ == "__main__":
    main()
