import re


def normalize_title(title: str) -> str:

    if not title:
        return ""

    title = title.lower()

    title = re.sub(r"[^\w\s]", "", title)

    title = re.sub(r"\s+", " ", title)

    return title.strip()