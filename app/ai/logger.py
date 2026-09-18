import time

from app.config import AI_LOGGING


class AILogger:
    """
    AI Worker performans logger.

    Ölçülen süreler:

    - Prompt hazırlama
    - Ollama
    - JSON Parse
    - Database Commit
    - Telegram
    - Toplam
    """

    def __init__(self):

        self.enabled = AI_LOGGING

        self.news_id = None
        self.model = None
        self.prompt_kb = 0.0

        self.total_start = time.perf_counter()

        self.prompt_time = 0.0
        self.ollama_time = 0.0
        self.parse_time = 0.0
        self.database_time = 0.0
        self.telegram_time = 0.0
        self.total_time = 0.0

    def set_news(self, news_id: int):

        self.news_id = news_id

    def set_model(self, model: str):

        self.model = model

    def set_prompt_size(self, kb: float):

        self.prompt_kb = kb

    def set_prompt_time(self, seconds: float):

        self.prompt_time = seconds

    def set_ollama_time(self, seconds: float):

        self.ollama_time = seconds

    def set_parse_time(self, seconds: float):

        self.parse_time = seconds

    def set_database_time(self, seconds: float):

        self.database_time = seconds

    def set_telegram_time(self, seconds: float):

        self.telegram_time = seconds

    def finish(self):

        self.total_time = (
            time.perf_counter() - self.total_start
        )

    def print(self):

        if not self.enabled:
            return

        print()

        print("🤖 AI Worker")

        print()

        print(f"📰 Haber ID      : {self.news_id}")

        print(f"🤖 Model         : {self.model}")

        print(f"📄 Prompt        : {self.prompt_kb:.2f} KB")

        print(
            f"⏱️ Prompt        : {self.prompt_time:.2f} sn"
        )

        print(
            f"⏱️ Ollama        : {self.ollama_time:.2f} sn"
        )

        print(
            f"🧠 Parse         : {self.parse_time:.2f} sn"
        )

        print(
            f"💾 Database      : {self.database_time:.2f} sn"
        )

        print(
            f"📨 Telegram      : {self.telegram_time:.2f} sn"
        )

        print(
            f"✅ Toplam         : {self.total_time:.2f} sn"
        )

        print()