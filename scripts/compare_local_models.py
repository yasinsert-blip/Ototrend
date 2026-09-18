"""Read-only news benchmark; writes results only under logs/model-comparison.

Run each model separately, using the same frozen 20-news sample. Never imports
main, starts workers, updates news, changes .env or selects the production model.
"""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests
from app.ai.cleaner import clean_text
from app.ai.pipeline import PROMPT_TEMPLATE
from app.ai.provider import SYSTEM_PROMPT
from app.ai.turkish_quality import normalize_analysis_result, validate_turkish_analysis
from app.config import (
    OLLAMA_NUM_CTX, OLLAMA_NUM_PREDICT, OLLAMA_TEMPERATURE,
    OLLAMA_TOP_K, OLLAMA_TOP_P,
)

CATEGORIES = set("EV Hybrid ICE SUV Sedan Hatchback Pickup Battery Charging Software Recall Factory Motorsport Financial Other".split())
FIELDS = {"title_tr", "summary_tr", "brand", "model", "category", "importance"}


def inspect_output(raw):
    """Strict JSON/schema checks, plus the app's heuristic language check."""
    errors = []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {"json_ok": False, "schema_ok": False, "language_ok": False, "errors": ["Invalid JSON"], "parsed": None}
    if not isinstance(value, dict):
        return {"json_ok": True, "schema_ok": False, "language_ok": False, "errors": ["Not an object"], "parsed": value}
    if set(value) != FIELDS:
        errors.append("Missing or extra fields")
    if any(not isinstance(value.get(key), str) for key in FIELDS - {"importance"}):
        errors.append("Non-string text field")
    if not isinstance(value.get("category"), str) or value["category"] not in CATEGORIES:
        errors.append("Invalid category")
    score = value.get("importance")
    if type(score) is not int or not 1 <= score <= 10:
        errors.append("Invalid importance")
    language_errors = validate_turkish_analysis(normalize_analysis_result(value))
    return dict(json_ok=True, schema_ok=not errors, language_ok=not language_errors,
                errors=errors + language_errors, parsed=value)


def freeze_samples(database, count):
    # mode=ro refuses to create a missing database and forbids writes.
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,title,content,source,link FROM news WHERE status != 'deleted' ORDER BY id DESC LIMIT 1000").fetchall()
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        text = clean_text(row["content"] or row["title"])
        if len(text) < 100 or text in seen:
            continue
        seen.add(text)
        groups[row["source"] or "Unknown"].append(dict(
            id=row["id"], title=row["title"], source=row["source"], link=row["link"], input=text,
        ))
    samples = []
    while len(samples) < count and any(groups.values()):
        for group in groups.values():
            if group and len(samples) < count:
                samples.append(group.pop(0))
    if len(samples) != count:
        raise RuntimeError(f"Only {len(samples)} suitable news items; expected {count}")
    return samples


def aggregate(rows):
    good = [row for row in rows if row.get("schema_ok") and row.get("language_ok")]
    times = [row["wall_seconds"] for row in rows]
    return dict(count=len(rows), json_ok=sum(row.get("json_ok", False) for row in rows),
                schema_ok=sum(row.get("schema_ok", False) for row in rows),
                heuristic_language_ok=sum(row.get("language_ok", False) for row in rows),
                accepted_first_attempt=len(good), mean_seconds=round(statistics.mean(times), 2),
                median_seconds=round(statistics.median(times), 2),
                total_seconds=round(sum(times), 2),
                seconds_per_accepted=round(sum(times) / len(good), 2) if good else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["gemma3:4b", "qwen3.5:4b"], required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "news.db")
    parser.add_argument("--output", type=Path, default=ROOT / "logs/model-comparison")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if urlsplit(args.host).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Benchmark only permits a local Ollama host")
    args.output.mkdir(parents=True, exist_ok=True)
    sample_path = args.output / "samples.json"
    if sample_path.exists():
        samples = json.loads(sample_path.read_text(encoding="utf-8"))
        if len(samples) != args.count:
            raise ValueError("Existing sample size differs; use a new output directory")
    else:
        samples = freeze_samples(args.database, args.count)
        sample_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    options = dict(num_ctx=OLLAMA_NUM_CTX, num_predict=OLLAMA_NUM_PREDICT,
                   temperature=OLLAMA_TEMPERATURE, top_k=OLLAMA_TOP_K, top_p=OLLAMA_TOP_P, seed=42)
    identity = dict(model=args.model, options=options, think=False if args.model.startswith("qwen") else None,
                    sample_sha256=hashlib.sha256(sample_path.read_bytes()).hexdigest(),
                    prompt_sha256=hashlib.sha256((SYSTEM_PROMPT + PROMPT_TEMPLATE).encode()).hexdigest())
    result_path = args.output / (args.model.replace(":", "-") + ".json")
    report = dict(identity=identity, started_at=datetime.now(timezone.utc).isoformat(), results=[],
                  method="One attempt per item, no retries. Frozen source-balanced latest news. Language check is heuristic, NOT factual accuracy. Models run serially; production is not paused.")
    if result_path.exists():
        report = json.loads(result_path.read_text(encoding="utf-8"))
        if report["identity"] != identity:
            raise ValueError("Benchmark settings changed; use a new output directory")
    with requests.Session() as session:
        session.trust_env = False
        for index in range(len(report["results"]), len(samples)):
            sample = samples[index]
            payload = dict(model=args.model, stream=False, format="json", keep_alive="5m", options=options,
                           messages=[dict(role="system", content=SYSTEM_PROMPT),
                                     dict(role="user", content=PROMPT_TEMPLATE.format(news=sample["input"]))])
            if identity["think"] is not None:
                payload["think"] = identity["think"]
            print(f"START {args.model} {index+1}/{len(samples)} news={sample['id']}", flush=True)
            start = time.perf_counter()
            fatal = False
            try:
                response = session.post(args.host + "/api/chat", json=payload, timeout=(10, 240))
                response.raise_for_status()
                data = response.json()
                raw = data.get("message", {}).get("content", "")
                row = dict(news_id=sample["id"], raw=raw, **inspect_output(raw))
                row.update({key: data.get(key) for key in (
                    "total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "done_reason")})
                row["thinking_chars"] = len(data.get("message", {}).get("thinking", ""))
            except (requests.RequestException, ValueError) as exc:
                row = dict(news_id=sample["id"], error=str(exc), json_ok=False, schema_ok=False, language_ok=False)
                fatal = True  # Stop on resource/connection errors rather than pile up more work.
            row["wall_seconds"] = round(time.perf_counter() - start, 3)
            report["results"].append(row)
            report["summary"] = aggregate(report["results"])
            report["completed"] = not fatal and len(report["results"]) == len(samples)
            result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"DONE {index+1}/{len(samples)} {row['wall_seconds']}s JSON={row['json_ok']} schema={row['schema_ok']} language={row['language_ok']}", flush=True)
            if fatal:
                raise RuntimeError(row["error"])
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
