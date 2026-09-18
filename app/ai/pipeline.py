import json
import time

from app.ai.cleaner import (
    clean_text,
    prompt_size_kb,
    debug_prompt,
)
from app.ai.provider import json_chat
from app.ai.parser import parse_json
from app.ai.turkish_quality import (
    normalize_analysis_result,
    validate_turkish_analysis,
)
from app.config import AI_TURKISH_QUALITY_RETRIES


PROMPT_TEMPLATE = """
Sen OtoTrendTR için çalışan deneyimli bir Türkçe otomotiv haber editörüsün.
Verilen kaynak metin İngilizce olabilir ve hatalı karakterler içerebilir.

Sadece geçerli JSON döndür.

{{
  "title_tr":"",
  "summary_tr":"",
  "brand":"",
  "model":"",
  "category":"",
  "importance":0
}}

Kurallar:

- title_tr: Doğal, anlamı korunmuş ve akıcı Türkçe haber başlığı yaz. Marka ve
  model adları dışında İngilizce kelime kullanma. Bozuk karakterleri, anlamsız
  işaretleri veya yabancı alfabe harflerini asla kopyalama.
- summary_tr: Haberi 1 veya 2 eksiksiz, doğal Türkçe cümleyle özgün biçimde
  özetle. Kaynakta olmayan bilgi ya da sayı ekleme. Metni birebir çevirme.
- brand: Marka
- model: Model
- category: EV, Hybrid, ICE, SUV, Sedan, Hatchback, Pickup, Battery, Charging, Software, Recall, Factory, Motorsport, Financial, Other
- importance: 1-10

Çıktı kuralları:
- Sadece JSON alanlarını döndür; açıklama veya Markdown ekleme.
- title_tr ve summary_tr mutlaka Türkçe olmalı.
- İngilizce kaynak başlığını veya bozuk kaynak karakterlerini aynen kullanma.
- Kaynak metin yetersizse tahmin etme; mevcut bilgiyi sade ve doğru Türkçeyle yaz.
- "tariff" için "gümrük vergisi" veya "gümrük tarifesi", "U.S." için
  "ABD", "car/vehicle" için "otomobil/araç" kullan.

Üslup örneği:
Kaynak: "Ford says U.S. tariffs will increase costs."
Türkçe: "Ford, ABD gümrük vergilerinin maliyetleri artıracağını açıkladı."

Haber:

{news}
"""


def _quality_retry_prompt(
    news: str,
    errors: list[str],
    draft: dict[str, object],
) -> str:
    previous_draft = json.dumps(
        {
            "title_tr": draft.get("title_tr", ""),
            "summary_tr": draft.get("summary_tr", ""),
        },
        ensure_ascii=False,
    )
    return (
        PROMPT_TEMPLATE.format(news=news)
        + "\nÖnceki taslak:\n"
        + previous_draft
        + "\nÖnceki taslak kabul edilmedi: "
        + "; ".join(errors)
        + ". Önceki taslaktaki yabancı kelimeleri ve anlamsız ifadeleri düzelt. "
        + "Bu kez yalnızca akıcı, anlamlı Türkçe ile yeniden yaz."
    )


def process(news: str):

    metrics = {
        "prompt_time": 0.0,
        "ollama_time": 0.0,
        "parse_time": 0.0,
        "prompt_kb": 0.0,
        "response_kb": 0.0,
    }

    # ==========================================================
    # Prompt
    # ==========================================================

    start = time.perf_counter()

    news = clean_text(news)

    prompt = PROMPT_TEMPLATE.format(
        news=news,
    )

    # DEBUG
    debug_prompt(
        news,
        prompt,
    )

    metrics["prompt_time"] = (
        time.perf_counter() - start
    )

    metrics["prompt_kb"] = prompt_size_kb(
        prompt
    )

    # ==========================================================
    # Ollama
    # ==========================================================

    start = time.perf_counter()

    result = None
    quality_errors: list[str] = []
    candidate: dict[str, object] = {}
    for attempt in range(AI_TURKISH_QUALITY_RETRIES + 1):
        request_prompt = prompt if attempt == 0 else _quality_retry_prompt(
            news,
            quality_errors,
            candidate,
        )
        response = json_chat(request_prompt)

        metrics["response_kb"] = round(
            len(response.encode("utf-8")) / 1024,
            2,
        )

        parse_start = time.perf_counter()
        try:
            candidate = normalize_analysis_result(parse_json(response))
        except ValueError as exc:
            metrics["parse_time"] += time.perf_counter() - parse_start
            quality_errors = [str(exc)]
            continue
        metrics["parse_time"] += time.perf_counter() - parse_start

        quality_errors = validate_turkish_analysis(candidate)
        if not quality_errors:
            result = candidate
            break

    metrics["ollama_time"] = time.perf_counter() - start
    metrics["quality_attempts"] = attempt + 1

    if result is None:
        raise ValueError(
            "AI Türkçe kalite kontrolünden geçemedi: "
            + "; ".join(quality_errors)
        )

    return result, metrics
