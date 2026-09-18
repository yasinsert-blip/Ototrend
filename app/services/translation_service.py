from typing import Dict

from app.ai.provider import chat


def translate_news(item: Dict) -> Dict:
    """
    Haber başlığı ve özetini Türkçeye çevirir.
    """

    title = item.get("title", "")
    summary = (
        item.get("description")
        or item.get("content")
        or ""
    )

    prompt = f"""
Sen profesyonel bir otomotiv editörüsün.

Aşağıdaki haberi doğal ve akıcı Türkçeye çevir.

Kurallar:

- Sadece çeviri yap.
- Bilgi ekleme.
- Yorum katma.
- Teknik terimleri koru.
- Marka ve model isimlerini değiştirme.

Çıktıyı aşağıdaki formatta ver.

TITLE:
<çeviri>

SUMMARY:
<çeviri>

Başlık:
{title}

Özet:
{summary}
"""

    try:
        response = chat(prompt)

        title_tr = ""
        summary_tr = ""

        if "SUMMARY:" in response:
            parts = response.split("SUMMARY:", 1)

            title_tr = (
                parts[0]
                .replace("TITLE:", "")
                .strip()
            )

            summary_tr = parts[1].strip()

        else:
            title_tr = response.strip()

        item["title_tr"] = title_tr
        item["summary_tr"] = summary_tr

    except Exception as e:

        print(f"❌ AI Çeviri Hatası: {e}")

        item["title_tr"] = None
        item["summary_tr"] = None

    return item