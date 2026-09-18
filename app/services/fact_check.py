"""Conservative source consistency checks, not a guarantee of factual truth.

No model calls or network requests. Unknown/ambiguous claims go to an editor.
"""
import re
import unicodedata
from decimal import Decimal


def normalized(text):
    return unicodedata.normalize("NFKC", str(text or "")).casefold().replace("ı", "i").replace("i\u0307", "i")


NUMBER = r"\d+(?:[.,]\d+)*"
SCALE = r"(?:million|milyon|billion|milyar|thousand|bin)"
CURRENCY = r"(?:usd|eur|try|tl|gbp|cny|dollars?|dolar|euros?|avro|lira|sterlin|yuan|[$€₺£])"
SCALES = {"million": 10**6, "milyon": 10**6, "billion": 10**9,
          "milyar": 10**9, "thousand": 1000, "bin": 1000}


def number_value(value, scale=None):
    # Accept English/Turkish decimal and thousands separators.
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", value):
        value = value.replace(",", "").replace(".", "")
    elif "," in value and "." in value:
        separator = "," if value.rfind(",") > value.rfind(".") else "."
        value = value.replace("." if separator == "," else ",", "").replace(separator, ".")
    else:
        value = value.replace(",", ".")
    try:
        return Decimal(value) * SCALES.get(scale, 1)
    except Exception:
        return value  # Unusual notation must not crash the queue.


def numbers(text):
    return {number_value(m[0], m[1]) for m in re.findall(
        rf"({NUMBER})(?:\s*({SCALE})\b)?", text
    )}


def currency_key(value):
    for key, aliases in {
        "USD": ("usd", "dollar", "dollars", "dolar", "$"),
        "EUR": ("eur", "euro", "euros", "avro", "€"),
        "TRY": ("try", "tl", "lira", "₺"),
        "GBP": ("gbp", "sterlin", "£"),
        "CNY": ("cny", "yuan"),
    }.items():
        if value in aliases:
            return key
    return value


def prices(text):
    found = set()
    for match in re.finditer(rf"({CURRENCY})\s*({NUMBER})(?:\s*({SCALE})\b)?", text):
        found.add((currency_key(match[1]), number_value(match[2], match[3])))
    for match in re.finditer(rf"({NUMBER})(?:\s*({SCALE})\b)?\s*({CURRENCY})(?!\w)", text):
        found.add((currency_key(match[3]), number_value(match[1], match[2])))
    return found


MONTHS = [
    ("january", "ocak"), ("february", "şubat"), ("march", "mart"),
    ("april", "nisan"), ("may", "mayis"), ("june", "haziran"),
    ("july", "temmuz"), ("august", "ağustos"), ("september", "eylül"),
    ("october", "ekim"), ("november", "kasim"), ("december", "aralik"),
]


def dates(text):
    result = set()
    for index, aliases in enumerate(MONTHS, 1):
        month = "(?:" + "|".join(aliases) + ")"
        for m in re.finditer(rf"\b(\d{{1,2}})\s+{month}(?:\s+(\d{{4}}))?\b", text):
            result.add((index, int(m[1]), m[2]))
        for m in re.finditer(rf"\b{month}\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b", text):
            result.add((index, int(m[1]), m[2]))
    return result


def check_facts(source, draft):
    source = normalized(source)
    output = normalized(" ".join(str(draft.get(k) or "") for k in (
        "title_tr", "summary_tr", "instagram_title", "instagram_caption"
    )))
    issues = []
    # Limited vocabulary: catch common brands even when the model omits the
    # structured brand field. Do not pretend this covers every manufacturer.
    for brand in ("audi", "bmw", "byd", "tesla", "toyota", "volkswagen", "ford",
                  "renault", "dacia", "hyundai", "kia", "honda", "nissan", "volvo",
                  "polestar", "togg", "fiat", "peugeot", "citroën", "skoda", "porsche"):
        pattern = r"(?<!\w)" + re.escape(brand) + r"(?!\w)"
        if re.search(pattern, output) and not re.search(pattern, source):
            issues.append(f"Metindeki marka kaynakta doğrulanamadı: {brand}")
    model_pattern = r"\b[a-z]{1,5}[-.]?\d{1,4}[a-z]{0,3}\b"
    new_models = set(re.findall(model_pattern, output)) - set(re.findall(model_pattern, source))
    if new_models:
        issues.append("Model/kod kaynakta doğrulanamadı: " + ", ".join(sorted(new_models)))
    for field, label in (("brand", "Marka"), ("model", "Model")):
        value = normalized(draft.get(field)).strip()
        if value and value not in ("none", "null", "unknown", "other", "bilinmiyor", "belirtilmemiş", "-", "n/a"):
            if not re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", source):
                issues.append(f"{label} kaynakta doğrulanamadı: {draft[field]}")
    unsupported = numbers(output) - numbers(source)
    if unsupported:
        issues.append("Kaynakta bulunmayan sayı/tarih: " + ", ".join(sorted(map(str, unsupported))))
    for currency, amount in sorted(prices(output) - prices(source), key=str):
        issues.append(f"Fiyat–para birimi eşleşmesi doğrulanamadı: {amount} {currency}")
    source_dates = dates(source)
    for month, day, year in dates(output):
        if not any(m == month and d == day and (year is None or y == year) for m, d, y in source_dates):
            issues.append(f"Tarih kaynakla eşleşmedi: {day}.{month}" + (f".{year}" if year else ""))
    return issues


def apply_fact_check(news, draft):
    issues = check_facts((news.title or "") + "\n" + (news.content or ""), draft)
    news.fact_check_notes = "\n".join(issues) or None
    if issues:
        news.status = "editor_review"
    return issues
