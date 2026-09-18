from contextlib import asynccontextmanager
import os
import sys

# Uvicorn Windows'ta yönlendirilmiş bir günlük dosyasına yazarken cp1254
# kullanabilir. Kaynak kayıtlarındaki Unicode simgeler, uygulamanın açılışını
# kesintiye uğratmamalıdır.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="backslashreplace")

from dotenv import load_dotenv

# Ortam değişkenleri, veritabanı ve router modülleri içe aktarılmadan önce
# yüklenmelidir. Aksi halde yerel .env içindeki DATABASE_URL yok sayılır.
load_dotenv(dotenv_path=os.path.join(os.environ['OTOTREND_DATA_DIR'], '.env') if os.getenv('OTOTREND_DATA_DIR') else None)

from app.views.dashboard_api import router as dashboard_api_router
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.ai.warmup import warmup
from app.config import RUN_SCHEDULER, SECRET_KEY
from app.database.database import Base, engine
from app.database.schema import ensure_database_upgrades
from app.database.source_seed import seed_sources
from app.scheduler.news_scheduler import start_scheduler, stop_scheduler

# ==========================================================
# Views
# ==========================================================

from app.views.auth import router as auth_router
from app.views.dashboard import router as dashboard_router
from app.views.news import router as news_router
from app.views.sources import router as source_router
from app.views.workflow import router as workflow_router

# ==========================================================
# API
# ==========================================================

from app.api.news import router as api_news_router
from app.api.source import router as api_source_router
from app.api.ai import router as ai_router


Base.metadata.create_all(bind=engine)
ensure_database_upgrades()


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("🚀 OtoTrend AI başlatılıyor...")

    # ==========================================================
    # Database
    # ==========================================================

    seed_sources()
    from app.services.ai_timing import recover_interrupted_runs
    recover_interrupted_runs()

    if RUN_SCHEDULER:
        warmup()
        start_scheduler()

    yield

    if RUN_SCHEDULER:
        stop_scheduler()

    print("🛑 OtoTrend AI durduruldu.")


app = FastAPI(
    title="OtoTrend AI CMS",
    version="2.1.0",
    lifespan=lifespan,
)

# ==========================================================
# Session Middleware
# ==========================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=os.getenv("APP_ENV", "development").lower() == "production",
)

if os.getenv('OTOTREND_DATA_DIR'):
    from pathlib import Path
    _generated = Path(os.environ['OTOTREND_DATA_DIR']) / 'generated'
    _generated.mkdir(parents=True, exist_ok=True)
    app.mount('/static/generated', StaticFiles(directory=str(_generated)), name='generated')

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)
# ==========================================================
# Views
# ==========================================================

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(news_router)
app.include_router(source_router)
app.include_router(workflow_router)

# ==========================================================
# API
# ==========================================================

app.include_router(api_news_router)
app.include_router(api_source_router)
app.include_router(ai_router)
app.include_router(dashboard_api_router)
