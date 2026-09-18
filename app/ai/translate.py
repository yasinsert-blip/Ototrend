from app.ai.provider import chat
from app.ai.prompts import TRANSLATE_PROMPT


def translate(text: str) -> str:

    prompt = f"""
{TRANSLATE_PROMPT}

İngilizce Haber:

{text}

Türkçe Haber:
"""

    return chat(prompt)