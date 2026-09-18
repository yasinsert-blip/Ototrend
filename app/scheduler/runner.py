"""Standalone process for the scheduled news and AI jobs."""

import signal
import threading

from app.ai.warmup import warmup
from app.database.database import Base, engine
from app.database.source_seed import seed_sources
from app.scheduler.news_scheduler import start_scheduler, stop_scheduler


shutdown_requested = threading.Event()


def request_shutdown(signum, frame):
    shutdown_requested.set()


def main():
    Base.metadata.create_all(bind=engine)
    seed_sources()
    warmup()
    start_scheduler()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    shutdown_requested.wait()
    stop_scheduler()


if __name__ == "__main__":
    main()
