"""Read-only Telegram configuration check; never sends messages or prints secrets."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import requests


if __name__ == "__main__":
    success = True
    for method, params in (("getMe", {}), ("getChat", {"chat_id": TELEGRAM_CHAT_ID})):
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
                params=params, timeout=15,
            )
            valid = response.status_code == 200 and response.json().get("ok") is True
            print(f"{method}: {'OK' if valid else 'FAILED'} (HTTP {response.status_code})")
            success = success and valid
        except Exception as error:
            print(f"{method}: FAILED ({type(error).__name__})")
            success = False
    raise SystemExit(0 if success else 1)
