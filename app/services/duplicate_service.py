from difflib import SequenceMatcher

from app.utils.text import normalize_title


def is_similar(title1: str, title2: str, threshold=0.88):

    t1 = normalize_title(title1)
    t2 = normalize_title(title2)

    ratio = SequenceMatcher(
        None,
        t1,
        t2,
    ).ratio()

    return ratio >= threshold