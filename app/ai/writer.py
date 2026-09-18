from app.ai.provider import chat


def instagram_title(text: str):

    prompt = f"""
Aşağıdaki haber için dikkat çekici
Instagram başlığı üret.

Sadece başlığı yaz.

{text}
"""

    return chat(prompt)