import json
import re


def normalize_string(value):
    """
    String alanlarını güvenli hale getirir.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


def normalize_int(value, default=0):
    """
    Sayısal alanları güvenli hale getirir.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_json(text: str):
    """
    AI çıktısından JSON'u güvenli şekilde ayıklar.
    """

    text = text.strip()

    # ```json ... ``` bloğunu kaldır
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    # JSON bloğunu bul
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("AI JSON döndürmedi.")

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Geçersiz JSON: {e}")
    # ==========================================================
    # Normalize
    # ==========================================================

    data["title_tr"] = normalize_string(data.get("title_tr"))
    data["summary_tr"] = normalize_string(data.get("summary_tr"))
    data["brand"] = normalize_string(data.get("brand"))
    data["model"] = normalize_string(data.get("model"))
    data["category"] = normalize_string(data.get("category"))
    data["importance"] = normalize_int(data.get("importance"))

    return data