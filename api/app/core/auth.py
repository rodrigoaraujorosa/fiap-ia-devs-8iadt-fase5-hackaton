"""Acesso ao ImobiQ: usuários convidados (e-mail e senha ou conta Google), com papel, e a senha de administrador
do .env como acesso de emergência.

Sem ADMIN_PASSWORD e sem credenciais do Google (ambiente local e testes), tudo fica liberado como administrador.
Com qualquer um dos dois, as telas internas exigem sessão: um token assinado (HMAC), válido por 12 horas, que o
navegador guarda num cookie HttpOnly (o JavaScript da página não o lê). A chave da assinatura deriva dos segredos
do .env: trocar a senha de administrador ou o SESSION_SECRET encerra todas as sessões.

Papéis: admin (tudo), gestor (todos os leads e a observabilidade), corretor (só os leads e visitas dele) e
visualizador (tudo o que o gestor vê, só leitura). O chat do visitante, o widget e o Telegram não passam por aqui.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole

TOKEN_HOURS = 12
COOKIE = "imobiq_session"
ADMIN_SUBJECT = "admin"  # sessão aberta com a senha de administrador, sem usuário no banco


@dataclass(frozen=True)
class Principal:
    """Quem está fazendo a requisição."""

    role: str
    name: str
    email: str | None = None
    picture: str | None = None
    user_id: int | None = None
    broker_id: int | None = None

    @property
    def sees_all(self) -> bool:
        return self.role != UserRole.CORRETOR

    @property
    def can_write(self) -> bool:
        return self.role != UserRole.VISUALIZADOR


LOCAL_ADMIN = Principal(role=UserRole.ADMIN, name="Acesso local (sem login)")
PASSWORD_ADMIN = Principal(role=UserRole.ADMIN, name="Administrador (senha)")


def password_enabled() -> bool:
    return bool(get_settings().admin_password)


def google_enabled() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def admin_required() -> bool:
    """Há algum login configurado? Sem nenhum, o app fica aberto (ambiente local)."""
    return password_enabled() or google_enabled()


def _sign(payload: str) -> str:
    s = get_settings()
    material = f"imobiq-session:{s.session_secret or ''}:{s.admin_password or ''}:{s.google_client_secret or ''}"
    return hmac.new(hashlib.sha256(material.encode()).digest(), payload.encode(), hashlib.sha256).hexdigest()


def check_password(password: str) -> bool:
    expected = get_settings().admin_password or ""
    return bool(expected) and hmac.compare_digest(password.encode(), expected.encode())


def issue_token(subject: str = ADMIN_SUBJECT) -> tuple[str, int]:
    """Token "<expira>.<quem>.<assinatura>": quem = "admin" (senha) ou o id do usuário."""
    expires_at = int(time.time()) + TOKEN_HOURS * 3600
    payload = f"{expires_at}.{subject}"
    return f"{payload}.{_sign(payload)}", expires_at


def token_subject(token: str | None) -> str | None:
    parts = (token or "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or int(parts[0]) < time.time():
        return None
    return parts[1] if hmac.compare_digest(parts[2], _sign(f"{parts[0]}.{parts[1]}")) else None


def _fingerprint(password_hash: str | None) -> str:
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def issue_link_token(user_id: int, password_hash: str | None, hours: int) -> str:
    """Link de definir/redefinir senha: "<expira>.<usuário>.<marca da senha atual>.<assinatura>".

    A marca muda quando a senha muda, então o link vale uma vez só (e um link antigo morre ao gerar senha nova).
    """
    payload = f"{int(time.time()) + hours * 3600}.{user_id}.{_fingerprint(password_hash)}"
    return f"{payload}.{_sign(f'senha:{payload}')}"


def _link_parts(token: str | None) -> list[str] | None:
    parts = (token or "").split(".")
    if len(parts) != 4 or not parts[0].isdigit() or not parts[1].isdigit() or int(parts[0]) < time.time():
        return None
    return parts if hmac.compare_digest(parts[3], _sign(f"senha:{'.'.join(parts[:3])}")) else None


def link_token_user_id(token: str | None) -> int | None:
    parts = _link_parts(token)
    return int(parts[1]) if parts else None


def link_token_matches(token: str | None, password_hash: str | None) -> bool:
    parts = _link_parts(token)
    return bool(parts) and hmac.compare_digest(parts[2], _fingerprint(password_hash))


def token_valid(token: str | None) -> bool:
    return not admin_required() or token_subject(token) is not None


def bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=TOKEN_HOURS * 3600,
        httponly=True,
        secure=get_settings().public_app_url.startswith("https"),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def principal_of(user: User) -> Principal:
    return Principal(role=user.role, name=user.name or user.email, email=user.email, picture=user.picture,
                     user_id=user.id, broker_id=user.broker_id)  # fmt: skip


def optional_principal(
    request: Request, authorization: str | None = Header(None), db: Session = Depends(get_db)
) -> Principal | None:
    """Quem está logado (cookie de sessão ou cabeçalho Authorization), ou None."""
    if not admin_required():
        return LOCAL_ADMIN
    subject = token_subject(request.cookies.get(COOKIE)) or token_subject(bearer(authorization))
    if subject is None:
        return None
    if subject == ADMIN_SUBJECT:
        return PASSWORD_ADMIN if password_enabled() else None
    user = db.get(User, int(subject)) if subject.isdigit() else None
    return principal_of(user) if user and user.active else None  # usuário desativado perde o acesso na hora


def current_principal(principal: Principal | None = Depends(optional_principal)) -> Principal:
    if principal is None:
        raise HTTPException(401, "Acesso restrito: entre com a sua conta")
    return principal


def require_role(*roles: str):
    """Dependência: exige login e um dos papéis informados."""

    def check(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(403, "Seu perfil não tem acesso a esta área")
        return principal

    return check


require_admin = require_role(UserRole.ADMIN)
require_insights = require_role(UserRole.ADMIN, UserRole.GESTOR, UserRole.VISUALIZADOR)  # observabilidade
