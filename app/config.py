import os
import secrets

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.environ['OTOTREND_DATA_DIR'], '.env') if os.getenv('OTOTREND_DATA_DIR') else None)

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# ==========================================================
# Telegram
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# Yeni bildirimlerin başlangıç anı. Boş bırakıldığında geçmiş haberler için
# toplu Telegram gönderimi yapılmaz.
TELEGRAM_NOTIFY_AFTER = os.getenv("TELEGRAM_NOTIFY_AFTER", "").strip()


def _require_env(name: str, value: str | None) -> str:
    if not value or not value.strip():
        raise RuntimeError(
            f"❌ Ortam değişkeni eksik: {name}\n"
            "Lütfen .env dosyanızı kontrol edin."
        )
    return value


TELEGRAM_BOT_TOKEN = (TELEGRAM_BOT_TOKEN or "") if APP_ENV == "desktop" else _require_env(
    "TELEGRAM_BOT_TOKEN",
    TELEGRAM_BOT_TOKEN,
)

TELEGRAM_CHAT_ID = (TELEGRAM_CHAT_ID or "") if APP_ENV == "desktop" else _require_env(
    "TELEGRAM_CHAT_ID",
    TELEGRAM_CHAT_ID,
)

# Development uses a temporary key; production must receive a stable key from
# the hosting environment so users are not logged out after every restart.
SECRET_KEY = os.getenv("SECRET_KEY")
if IS_PRODUCTION or APP_ENV == "desktop":
    SECRET_KEY = _require_env("SECRET_KEY", SECRET_KEY)
elif not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)

RUN_SCHEDULER = env_flag("RUN_SCHEDULER", default=True)
OLLAMA_HOST = os.getenv("OLLAMA_HOST")

# ==========================================================
# Haber saklama politikası
# ==========================================================

# Haberler ilk 90 gün normal iş akışında kalır. Bu sürenin sonunda
# arşivlenir; bir yılı geçen arşiv kayıtları ise önce SQLite yedeği
# alındıktan sonra temizlenir.
NEWS_RETENTION_ENABLED = env_flag("NEWS_RETENTION_ENABLED", default=True)
NEWS_ARCHIVE_AFTER_DAYS = int(os.getenv("NEWS_ARCHIVE_AFTER_DAYS", "90"))
NEWS_DELETE_AFTER_DAYS = int(os.getenv("NEWS_DELETE_AFTER_DAYS", "365"))

if NEWS_ARCHIVE_AFTER_DAYS < 1:
    raise RuntimeError("NEWS_ARCHIVE_AFTER_DAYS en az 1 olmalıdır.")
if NEWS_DELETE_AFTER_DAYS <= NEWS_ARCHIVE_AFTER_DAYS:
    raise RuntimeError(
        "NEWS_DELETE_AFTER_DAYS, NEWS_ARCHIVE_AFTER_DAYS değerinden büyük olmalıdır."
    )

# Aynı kaynak art arda başarısız olursa, sistem boşuna tekrar denemek yerine
# kaynağı güvenli biçimde pasife alır. Editör kaynağı panelden yeniden açabilir.
SOURCE_AUTO_DISABLE_FAILURES = int(
    os.getenv("SOURCE_AUTO_DISABLE_FAILURES", "3")
)
if SOURCE_AUTO_DISABLE_FAILURES < 1:
    raise RuntimeError("SOURCE_AUTO_DISABLE_FAILURES en az 1 olmalıdır.")

# Genel RSS kaynakları ağ ağırlıklıdır. Aynı anda sınırlı sayıda okunmaları,
# tarama turunu kısaltırken yayıncıları gereksiz istek yüküyle karşılamaz.
RSS_FETCH_WORKERS = int(os.getenv("RSS_FETCH_WORKERS", "4"))
NEWS_SCAN_INTERVAL_MINUTES = int(
    os.getenv("NEWS_SCAN_INTERVAL_MINUTES", "5")
)
if RSS_FETCH_WORKERS < 1:
    raise RuntimeError("RSS_FETCH_WORKERS en az 1 olmalıdır.")
if NEWS_SCAN_INTERVAL_MINUTES < 1:
    raise RuntimeError("NEWS_SCAN_INTERVAL_MINUTES en az 1 olmalıdır.")

# ==========================================================
# AI Configuration
# ==========================================================

# "auto" seçildiğinde OPENAI_API_KEY varsa OpenAI, yoksa mevcut Ollama
# kurulumu kullanılır. "openai" seçimi anahtar yoksa açık bir hata verir.
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6").strip()
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "120"))

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gemma3:4b",
)

AI_BATCH_SIZE = int(
    os.getenv(
        "AI_BATCH_SIZE",
        "1",
    )
)

# Yerel CPU ile çalışan model için kısa ve tekil turlar, büyük paralel
# paketlerden daha kararlı çalışır. Hatalı içerikler kontrollü aralıklarla
# yeniden denenir; sonrasında editörün manuel kararına bırakılır.
AI_WORKER_INTERVAL_SECONDS = int(
    os.getenv("AI_WORKER_INTERVAL_SECONDS", "150")
)
AI_MAX_ATTEMPTS = int(os.getenv("AI_MAX_ATTEMPTS", "3"))
AI_RETRY_DELAY_MINUTES = int(os.getenv("AI_RETRY_DELAY_MINUTES", "15"))

MAX_CONTENT_LENGTH = int(
    os.getenv(
        "MAX_CONTENT_LENGTH",
        "800",
    )
)

AI_TIMEOUT = int(
    os.getenv(
        "AI_TIMEOUT",
        "120",
    )
)

AI_LOGGING = (
    os.getenv(
        "AI_LOGGING",
        "true",
    ).lower()
    == "true"
)
OLLAMA_KEEP_ALIVE = os.getenv(
    "OLLAMA_KEEP_ALIVE",
    "30m",
)

OLLAMA_NUM_CTX = int(
    os.getenv(
        "OLLAMA_NUM_CTX",
        "4096",
    )
)
if AI_TIMEOUT < 1:
    raise RuntimeError("AI_TIMEOUT en az 1 saniye olmalıdır.")

# AI kuyruğu yalnızca güncel haberleri işler. AI puanı yeterince yüksek olan
# içerikler editöryal inceleme için hazırlanır; diğerleri geçmişte aranabilir
# biçimde saklanır ama editör kuyruğunu doldurmaz.
AI_QUEUE_MAX_AGE_HOURS = int(
    os.getenv("AI_QUEUE_MAX_AGE_HOURS", "24")
)
AI_REVIEW_MIN_IMPORTANCE = int(
    os.getenv("AI_REVIEW_MIN_IMPORTANCE", "8")
)
AI_TURKISH_QUALITY_RETRIES = int(
    os.getenv("AI_TURKISH_QUALITY_RETRIES", "1")
)

if AI_QUEUE_MAX_AGE_HOURS < 1:
    raise RuntimeError("AI_QUEUE_MAX_AGE_HOURS en az 1 olmalıdır.")
if not 0 <= AI_REVIEW_MIN_IMPORTANCE <= 10:
    raise RuntimeError("AI_REVIEW_MIN_IMPORTANCE 0 ile 10 arasında olmalıdır.")
if AI_TURKISH_QUALITY_RETRIES < 0:
    raise RuntimeError("AI_TURKISH_QUALITY_RETRIES negatif olamaz.")
if AI_BATCH_SIZE < 1:
    raise RuntimeError("AI_BATCH_SIZE en az 1 olmalıdır.")
if AI_WORKER_INTERVAL_SECONDS < 30:
    raise RuntimeError("AI_WORKER_INTERVAL_SECONDS en az 30 olmalıdır.")
if AI_MAX_ATTEMPTS < 1:
    raise RuntimeError("AI_MAX_ATTEMPTS en az 1 olmalıdır.")
if AI_RETRY_DELAY_MINUTES < 1:
    raise RuntimeError("AI_RETRY_DELAY_MINUTES en az 1 olmalıdır.")

OLLAMA_TEMPERATURE = float(
    os.getenv(
        "OLLAMA_TEMPERATURE",
        "0.2",
    )
)
# ==========================================================
# Ollama Advanced Configuration
# ==========================================================

OLLAMA_NUM_PREDICT = int(
    os.getenv(
        "OLLAMA_NUM_PREDICT",
        "120",
    )
)

# Instagram üretimi başlık ve açıklama alanlarını birlikte döndürür. Genel
# sohbet sınırını yükseltmeden, bu akış için yeterli ve öngörülebilir bir
# yanıt bütçesi kullanılır.
INSTAGRAM_NUM_PREDICT = int(
    os.getenv(
        "INSTAGRAM_NUM_PREDICT",
        "320",
    )
)

OLLAMA_TOP_K = int(
    os.getenv(
        "OLLAMA_TOP_K",
        "20",
    )
)

OLLAMA_TOP_P = float(
    os.getenv(
        "OLLAMA_TOP_P",
        "0.8",
    )
)
