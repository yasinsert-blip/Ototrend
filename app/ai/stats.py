from dataclasses import dataclass


@dataclass
class AIStats:

    processed: int = 0
    success: int = 0
    failed: int = 0

    total_prompt_kb: float = 0.0
    total_response_kb: float = 0.0

    total_duration: float = 0.0

    model: str = ""


stats = AIStats()


def reset():

    global stats

    stats = AIStats()


def add_success(
    *,
    model: str,
    prompt_kb: float,
    response_kb: float,
    duration: float,
):

    stats.processed += 1
    stats.success += 1

    stats.model = model

    stats.total_prompt_kb += prompt_kb
    stats.total_response_kb += response_kb

    stats.total_duration += duration


def add_failure():

    stats.processed += 1
    stats.failed += 1


def summary():

    avg_duration = (
        stats.total_duration / stats.success
        if stats.success
        else 0
    )

    avg_prompt = (
        stats.total_prompt_kb / stats.success
        if stats.success
        else 0
    )

    avg_response = (
        stats.total_response_kb / stats.success
        if stats.success
        else 0
    )

    return {

        "processed": stats.processed,

        "success": stats.success,

        "failed": stats.failed,

        "model": stats.model,

        "average_duration": round(
            avg_duration,
            2,
        ),

        "average_prompt_kb": round(
            avg_prompt,
            2,
        ),

        "average_response_kb": round(
            avg_response,
            2,
        ),

    }


def print_summary():

    data = summary()

    print()

    print("📊 AI Statistics")

    print()

    print(f"Toplam İşlem     : {data['processed']}")
    print(f"Başarılı         : {data['success']}")
    print(f"Başarısız        : {data['failed']}")
    print(f"Model            : {data['model']}")
    print(f"Ort. Süre        : {data['average_duration']} sn")
    print(f"Ort. Prompt      : {data['average_prompt_kb']} KB")
    print(f"Ort. Yanıt       : {data['average_response_kb']} KB")

    print()