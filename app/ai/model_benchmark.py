import json
import time

import ollama

TEST_NEWS = """
Volkswagen unveiled its cheapest electric SUV, the ID. Cross.

The new model offers up to 430 km of driving range,
supports 175 kW DC fast charging,
and is expected to become Volkswagen's entry-level EV.

Return ONLY valid JSON.
"""

PROMPT = f"""
Türkçe otomotiv editörü olarak aşağıdaki haberi analiz et.

Kurallar:

- title_tr : Türkçe başlık
- summary_tr : En fazla 2 cümle
- brand
- model
- category
- importance (1-10)

category yalnızca:

EV
Hybrid
ICE
SUV
Sedan
Hatchback
Pickup
Battery
Charging
Software
Recall
Factory
Motorsport
Financial
Other

Sadece JSON döndür.

{{
    "title_tr":"",
    "summary_tr":"",
    "brand":"",
    "model":"",
    "category":"",
    "importance":0
}}

Haber:

{TEST_NEWS}
"""

MODELS = [
    "gemma3:4b",
    "qwen2.5:3b",
    "llama3.2:3b",
]


def benchmark(model: str):

    print("=" * 70)
    print(f"🤖 MODEL : {model}")
    print("=" * 70)

    start = time.perf_counter()

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": PROMPT,
            }
        ],
        options={
            "temperature": 0.2,
            "num_ctx": 2048,
            "num_predict": 180,
        },
        keep_alive="30m",
    )

    elapsed = time.perf_counter() - start

    text = response.message.content.strip()

    print(f"⏱️ Süre : {elapsed:.2f} sn")
    print(f"📦 Boyut : {len(text)} karakter")

    try:

        data = json.loads(text)

        print("✅ JSON Geçerli")

        print(f"Başlık     : {data.get('title_tr')}")
        print(f"Marka      : {data.get('brand')}")
        print(f"Model      : {data.get('model')}")
        print(f"Kategori   : {data.get('category')}")
        print(f"Importance : {data.get('importance')}")

    except Exception as e:

        print("❌ JSON Hatası")
        print(e)

        print()
        print(text)

    print()


def main():

    print()
    print("=" * 70)
    print("🚀 OtoTrend AI Model Benchmark")
    print("=" * 70)
    print()

    for model in MODELS:

        benchmark(model)


if __name__ == "__main__":

    main()