import os
import hmac

from fastapi import (
    APIRouter,
    Form,
    Request,
    status,
)

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import APP_ENV, _require_env
from app.services.user_service import authenticate_user


ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

if APP_ENV in ("production", "desktop"):
    ADMIN_USERNAME = _require_env("ADMIN_USERNAME", os.getenv("ADMIN_USERNAME"))
    ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD"))


# ==========================================================
# Router
# ==========================================================

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


# ==========================================================
# Login Page
# ==========================================================

@router.get("/login")
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error": None,
        },
    )


# ==========================================================
# Login
# ==========================================================

@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):

    user = authenticate_user(username, password)
    is_configured_admin = (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )

    if user is not None or is_configured_admin:

        request.session["authenticated"] = True
        request.session["username"] = (
            user.username if user is not None else ADMIN_USERNAME
        )

        return RedirectResponse(
            url="/",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error": "Kullanıcı adı veya şifre hatalı.",
        },
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


# ==========================================================
# Logout
# ==========================================================
@router.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )
