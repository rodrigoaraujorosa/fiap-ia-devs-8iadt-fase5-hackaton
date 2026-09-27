"""Acesso de administrador (tela de configurações e ações de demo).

Com ADMIN_PASSWORD vazio (ambiente local), tudo fica liberado. Com senha, o login devolve um token assinado
(HMAC com a própria senha como chave): trocar a senha no .env invalida todos os tokens emitidos.
"""

import hashlib
import hmac
import time

from fastapi import Header, HTTPException

from app.core.config import get_settings

TOKEN_HOURS = 12


def admin_required() -> bool:
    return bool(get_settings().admin_password)


def _sign(payload: str) -> str:
    key = hashlib.sha256(f"imobiq-admin:{get_settings().admin_password}".encode()).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def check_password(password: str) -> bool:
    expected = get_settings().admin_password or ""
    return bool(expected) and hmac.compare_digest(password.encode(), expected.encode())


def issue_token() -> tuple[str, int]:
    expires_at = int(time.time()) + TOKEN_HOURS * 3600
    return f"{expires_at}.{_sign(str(expires_at))}", expires_at


def token_valid(token: str | None) -> bool:
    if not admin_required():
        return True
    expires, _, signature = (token or "").partition(".")
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(signature, _sign(expires))


def bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_admin(authorization: str | None = Header(None)) -> None:
    """Dependência das rotas de administração: exige o token do login quando há ADMIN_PASSWORD."""
    if not token_valid(bearer(authorization)):
        raise HTTPException(401, "Acesso restrito: entre com a senha de administrador")
