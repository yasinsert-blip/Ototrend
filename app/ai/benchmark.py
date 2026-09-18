import statistics
import time

from app.ai.provider import chat
from app.config import OLLAMA_MODEL


TEST_PROMPT = """
You are an automotive expert.

Answer only with:

OK
"""


def run_benchmark(iterations: int = 10):
    """
    Ollama performans benchmarkı.

    Ölçülenler:

    - İlk çalışma (Cold Start)
    - En düşük süre
    - En yüksek süre
    - Ortalama süre
    """

    print("=" * 60)
    print("🚀 OtoTrend AI Benchmark")
    print("=" * 60)

    print(f"🤖 Model : {OLLAMA_MODEL}")
    print(f"🔁 Test  : {iterations} kez")
    print()

    times = []

    for i in range(iterations):

        print(f"[{i+1}/{iterations}] çalışıyor...")

        start = time.perf_counter()

        response = chat(TEST_PROMPT)

        elapsed = time.perf_counter() - start

        times.append(elapsed)

        print(
            f"⏱️ {elapsed:.2f} sn | "
            f"Cevap: {response[:50]}"
        )

        print()

    cold_start = times[0]

    warm_times = times[1:] if len(times) > 1 else times

    print("=" * 60)
    print("📊 SONUÇ")
    print("=" * 60)

    print(f"🥶 Cold Start : {cold_start:.2f} sn")

    print(
        f"⚡ Ortalama    : "
        f"{statistics.mean(warm_times):.2f} sn"
    )

    print(
        f"🚀 En Hızlı    : "
        f"{min(warm_times):.2f} sn"
    )

    print(
        f"🐢 En Yavaş    : "
        f"{max(warm_times):.2f} sn"
    )

    print()

    if statistics.mean(warm_times) > 20:

        print("⚠️ Performans düşük.")

        print(
            "Muhtemel nedenler:"
        )

        print("- CPU yetersiz")

        print("- Ollama ayarları")

        print("- Çok büyük context")

        print("- Model RAM'de kalmıyor")

    elif statistics.mean(warm_times) > 10:

        print("🟡 Performans orta seviyede.")

    else:

        print("🟢 Performans çok iyi.")

    print("=" * 60)


if __name__ == "__main__":

    run_benchmark()