import ollama
import requests
import httpx

from app.config import (
    AI_PROVIDER,
    AI_TIMEOUT,
    OLLAMA_HOST,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    INSTAGRAM_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_K,
    OLLAMA_TOP_P,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
)


client = ollama.Client(host=OLLAMA_HOST or None, timeout=httpx.Timeout(AI_TIMEOUT, connect=10.0))

SYSTEM_PROMPT = """
You are an API.

Return ONLY valid JSON.

Do not explain.

Do not use markdown.

Do not use ```.

Return exactly one JSON object.
"""


def _active_provider() -> str:
    if AI_PROVIDER == "auto":
        return "openai" if OPENAI_API_KEY else "ollama"
    if AI_PROVIDER in {"openai", "ollama"}:
        return AI_PROVIDER
    raise RuntimeError(
        "AI_PROVIDER yalnızca auto, openai veya ollama olabilir."
    )


def _openai_response(prompt: str, *, json_mode: bool = False) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OpenAI seçildi ancak OPENAI_API_KEY tanımlı değil."
        )

    payload: dict[str, object] = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT if json_mode else "",
        "input": prompt,
        # Haber metninin API tarafında saklanmaması tercih edilir.
        "store": False,
    }
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=OPENAI_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in {401, 403}:
            raise RuntimeError(
                "OpenAI API anahtarı veya proje yetkisi doğrulanamadı."
            ) from exc
        if status_code == 429:
            raise RuntimeError(
                "OpenAI proje kotası veya hız limiti aşıldı. Platformdaki "
                "faturalandırma ve kullanım limitlerini kontrol edin."
            ) from exc
        raise RuntimeError(
            "OpenAI API isteği reddedildi."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError("OpenAI API isteği başarısız oldu.") from exc
    finally:
        if "response" in locals():
            response.close()

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text", "")
                if isinstance(text, str) and text.strip():
                    return text.strip()

    raise RuntimeError("OpenAI API yanıtında metin bulunamadı.")


def chat(prompt: str) -> str:

    if _active_provider() == "openai":
        return _openai_response(prompt)

    response = client.chat(

        model=OLLAMA_MODEL,

        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],

        keep_alive=OLLAMA_KEEP_ALIVE,

        options={

            "num_ctx": OLLAMA_NUM_CTX,

            "temperature": OLLAMA_TEMPERATURE,

            "num_predict": OLLAMA_NUM_PREDICT,

            "top_k": OLLAMA_TOP_K,

            "top_p": OLLAMA_TOP_P,

        },

    )

    return response.message.content.strip()


def json_chat(prompt: str) -> str:
    """Haber analizinde şemalı JSON döndürülmesini zorunlu kılar."""
    if _active_provider() == "openai":
        return _openai_response(prompt, json_mode=True)

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        format="json",
        keep_alive=OLLAMA_KEEP_ALIVE,
        options={
            "num_ctx": OLLAMA_NUM_CTX,
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "top_k": OLLAMA_TOP_K,
            "top_p": OLLAMA_TOP_P,
        },
    )

    return response["message"]["content"].strip()


def instagram_chat(prompt: str) -> str:

    if _active_provider() == "openai":
        return _openai_response(prompt, json_mode=True)

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        # Yerel modelin açıklama/metin yerine geçerli bir JSON nesnesi
        # döndürmesini zorunlu kılar. Instagram akışı bu çıktıyı doğrudan
        # alanlara yerleştirdiği için bu ayar kritiktir.
        format="json",
        keep_alive=OLLAMA_KEEP_ALIVE,
        options={
            "num_ctx": OLLAMA_NUM_CTX,
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": INSTAGRAM_NUM_PREDICT,
            "top_k": OLLAMA_TOP_K,
            "top_p": OLLAMA_TOP_P,
        },
    )

    return response["message"]["content"].strip()
