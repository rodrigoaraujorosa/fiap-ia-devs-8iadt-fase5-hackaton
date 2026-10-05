import asyncio
import hmac
import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.core import auth, passwords
from app.core.config import get_settings
from app.db.session import get_db
from app.services import google_oauth, rate_limit, users

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["acesso"])

STATE_COOKIE = "imobiq_oauth_state"
LOGIN_ATTEMPTS_HOUR = 10  # por e-mail (ou por IP, na senha de administrador)
RESET_REQUESTS_HOUR = 3  # e-mails de redefinição por endereço
TOO_MANY = "Muitas tentativas. Aguarde alguns minutos e tente de novo."


class LoginIn(BaseModel):
    email: str | None = None  # sem e-mail: acesso de emergência com a senha de administrador
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class NewPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=passwords.MIN_LENGTH, max_length=passwords.MAX_LENGTH)
    accept_terms: bool = False  # obrigatório na criação da conta (quem ainda não aceitou os termos)


class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str | None
    picture: str | None
    role: str
    broker_id: int | None


class SessionOut(BaseModel):
    required: bool  # há login configurado (senha e/ou Google)
    google: bool
    password: bool
    user: Me | None  # quem está logado; sem login configurado, o administrador local


@router.get("/status")
def auth_status(authorization: str | None = Header(None)):
    """Se a área de administração exige senha e se o token enviado ainda vale."""
    return {"required": auth.admin_required(), "authenticated": auth.token_valid(auth.bearer(authorization))}


@router.get("/me", response_model=SessionOut)
def me(principal: auth.Principal | None = Depends(auth.optional_principal)):
    """Sessão atual: formas de login disponíveis e o usuário logado, com o papel (para o menu e as telas)."""
    return {
        "required": auth.admin_required(),
        "google": auth.google_enabled(),
        "password": auth.password_enabled(),
        "user": principal,
    }


@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Abre uma sessão de 12 horas: e-mail e senha do usuário, ou só a senha de administrador (emergência)."""
    email = (payload.email or "").strip().lower()
    who = email or rate_limit.client_ip(request) or "desconhecido"
    if not rate_limit.allow(f"login:{who}", LOGIN_ATTEMPTS_HOUR):
        raise HTTPException(429, TOO_MANY)
    if email:
        user = users.login_with_password(db, email, payload.password)
        if user is None:
            await asyncio.sleep(1)  # atrasa tentativas de adivinhar a senha
            raise HTTPException(401, "E-mail ou senha incorretos")
        subject = str(user.id)
    else:
        if not auth.password_enabled():
            raise HTTPException(404, "Área de administração sem senha configurada")
        if not auth.check_password(payload.password):
            await asyncio.sleep(1)
            raise HTTPException(401, "Senha incorreta")
        subject = auth.ADMIN_SUBJECT
    rate_limit.forget(f"login:{who}")  # entrou: as tentativas erradas anteriores não contam mais
    token, expires_at = auth.issue_token(subject)
    auth.set_session_cookie(response, token)
    return {"token": token, "expires_at": expires_at}


def _send_reset(email: str) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        user = users.by_email(db, email)
        if user and user.active:
            users.send_access_email(user, users.access_link(user, users.RESET_HOURS), invite=False)


@router.post("/forgot")
def forgot_password(payload: ForgotIn, tasks: BackgroundTasks):
    """Esqueci minha senha: manda o link por e-mail. A resposta é sempre a mesma, exista o e-mail ou não."""
    email = payload.email.strip().lower()
    if rate_limit.allow(f"forgot:{email}", RESET_REQUESTS_HOUR):
        tasks.add_task(_send_reset, email)
    return {"ok": True}


@router.get("/password")
def password_link_info(token: str, db: Session = Depends(get_db)):
    """Confere o link de definir/redefinir senha e diz de quem ele é (para a tela mostrar o e-mail)."""
    user = users.user_for_link(db, token)
    if user is None:
        raise HTTPException(400, "Este link expirou ou já foi usado. Peça um novo.")
    return {
        "email": user.email,
        "name": user.name,
        "has_password": user.has_password,
        "needs_terms": user.terms_accepted_at is None,  # a tela mostra a caixa de aceite
    }


@router.post("/password")
def define_password(payload: NewPasswordIn, response: Response, db: Session = Depends(get_db)):
    """Define a senha pelo link recebido e já abre a sessão. O link deixa de valer."""
    user = users.user_for_link(db, payload.token)
    if user is None:
        raise HTTPException(400, "Este link expirou ou já foi usado. Peça um novo.")
    if user.terms_accepted_at is None and not payload.accept_terms:
        raise HTTPException(422, "Para criar a conta, aceite os Termos de Uso e a Política de Privacidade.")
    users.set_password(db, user, payload.password, payload.accept_terms)
    token, _ = auth.issue_token(str(user.id))
    auth.set_session_cookie(response, token)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    auth.clear_session_cookie(response)
    return {"ok": True}


def _safe_next(path: str | None) -> str:
    """Só caminhos do próprio app: nunca redireciona para outro site depois do login."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path
    return "/dashboard"


def _back_to_app(path: str, error: str | None = None) -> RedirectResponse:
    url = f"{get_settings().public_app_url.rstrip('/')}{path}"
    if error:
        url += ("&" if "?" in url else "?") + urlencode({"auth_error": error})
    return RedirectResponse(url, status_code=303)


@router.get("/google/login")
def google_login(next: str | None = None):
    """Leva ao Google. O "state" (anti-CSRF) e a página de volta ficam num cookie de 10 minutos."""
    if not auth.google_enabled():
        raise HTTPException(404, "Login com Google não configurado")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(google_oauth.authorization_url(state), status_code=303)
    response.set_cookie(
        STATE_COOKIE,
        f"{state}|{_safe_next(next)}",
        max_age=600,
        httponly=True,
        secure=get_settings().public_app_url.startswith("https"),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None,
                    db: Session = Depends(get_db)):  # fmt: skip
    """Volta do Google: confere o state, troca o código pelo perfil e abre a sessão só para usuários convidados."""
    if not auth.google_enabled():
        raise HTTPException(404, "Login com Google não configurado")
    expected, _, next_path = request.cookies.get(STATE_COOKIE, "").partition("|")
    next_path = _safe_next(next_path)

    def finish(error_code: str | None = None, token: str | None = None) -> RedirectResponse:
        response = _back_to_app(next_path, error_code)
        response.delete_cookie(STATE_COOKIE, path="/")
        if token:
            auth.set_session_cookie(response, token)
        return response

    if error or not code:  # o usuário cancelou na tela do Google
        return finish("cancelado")
    if not expected or not state or not hmac.compare_digest(expected, state):
        return finish("expirado")
    try:
        profile = google_oauth.exchange(code)
    except google_oauth.GoogleAuthError as exc:
        log.warning("Login com Google falhou: %s", exc)
        return finish("google")
    user = users.login_with_google(db, profile)
    if user is None:
        log.warning("Login com Google recusado: conta sem convite ou desativada")
        return finish("nao_autorizado")
    token, _ = auth.issue_token(str(user.id))
    return finish(token=token)
