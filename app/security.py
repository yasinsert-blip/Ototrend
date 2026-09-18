"""Uygulama içi yönetim uç noktaları için ortak erişim kontrolleri."""

from fastapi import HTTPException, Request, status


def require_authenticated(request: Request) -> None:
    """Yalnızca oturum açmış CMS kullanıcılarının isteğe devam etmesine izin ver."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
