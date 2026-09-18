from app.models.source import Source


def calculate_health(source: Source) -> int:
    total = source.success_count + source.error_count

    if total == 0:
        return 100

    return int((source.success_count / total) * 100)


def summarize_source_health(sources: list[Source]) -> dict[str, int]:
    return {
        "total": len(sources),
        "active": sum(1 for source in sources if source.enabled),
        "auto_disabled": sum(
            1
            for source in sources
            if not source.enabled and source.auto_disabled_at is not None
        ),
        "needs_attention": sum(
            1
            for source in sources
            if source.enabled and source.consecutive_failures > 0
        ),
    }
