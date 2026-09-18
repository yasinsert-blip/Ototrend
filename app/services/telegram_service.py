import requests

from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


# ==========================================================
# Mesaj Gönder
# ==========================================================

def send_telegram_message(text) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }

    try:

        response = requests.post(
            url,
            data=data,
            timeout=15,
        )

        if response.status_code == 200 and response.json().get("ok") is True:

            print("📨 Telegram mesajı gönderildi.")
            return True

        else:

            print(
                "❌ Telegram Hatası:",
                response.status_code,
            )
            return False

    except Exception as e:

        print(
            "❌ Telegram Exception:",
            type(e).__name__,
        )
        return False


# ==========================================================
# Fotoğraflı Mesaj Gönder
# ==========================================================

def send_telegram_photo(photo_url, caption) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
    }

    try:

        response = requests.post(
            url,
            data=data,
            timeout=20,
        )

        if response.status_code == 200 and response.json().get("ok") is True:

            print("🖼️ Telegram fotoğrafı gönderildi.")
            return True

        else:

            print(
                "❌ Telegram Fotoğraf Hatası:",
                response.status_code,
            )

            # Fotoğraf gönderilemezse normal mesaj gönder
            return send_telegram_message(caption)

    except Exception as e:

        print(
            "❌ Telegram Exception:",
            type(e).__name__,
        )

        # Hata olursa yine mesaj gönder
        return send_telegram_message(caption)
