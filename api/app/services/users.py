"""Usuários do ImobiQ: quem pode entrar (com e-mail e senha ou com a conta Google) e com qual papel."""

import logging
import smtplib
from datetime import UTC, datetime
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auth, passwords
from app.core.config import get_settings
from app.models import User
from app.models.enums import UserRole
from app.services import mailer
from app.services.email_render import EmailContent

log = logging.getLogger(__name__)

INVITE_HOURS = 72  # validade do link de primeiro acesso
RESET_HOURS = 1  # validade do link de "esqueci minha senha"


def admin_emails() -> set[str]:
    """E-mails do ADMIN_EMAILS (.env): entram como admin no primeiro login com Google, sem convite."""
    return {e.strip().lower() for e in get_settings().admin_emails.split(",") if e.strip()}


def by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def _touch(db: Session, user: User) -> User:
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def login_with_google(db: Session, profile: dict) -> User | None:
    """Usuário autorizado para o perfil do Google, ou None (não convidado ou desativado)."""
    user = by_email(db, profile["email"])
    if user is None and profile["email"] in admin_emails():
        user = User(email=profile["email"], role=UserRole.ADMIN, active=True)
        db.add(user)
        log.info("Primeiro login de administrador (ADMIN_EMAILS)")
    if user is None or not user.active:
        return None
    user.name = profile.get("name") or user.name
    user.picture = profile.get("picture") or user.picture
    return _touch(db, user)


def login_with_password(db: Session, email: str, password: str) -> User | None:
    """Usuário ativo com essa senha, ou None. O hash é conferido mesmo sem usuário, para não revelar quem existe."""
    user = by_email(db, email)
    valid = passwords.verify_password(password, user.password_hash if user else None)
    return _touch(db, user) if user and user.active and valid else None


def access_link(user: User, hours: int) -> str:
    """Link de uso único para a pessoa definir (ou redefinir) a própria senha."""
    token = auth.issue_link_token(user.id, user.password_hash, hours)
    return f"{get_settings().public_app_url.rstrip('/')}/password?token={token}"


def user_for_link(db: Session, token: str) -> User | None:
    """Dono do link, se o link ainda vale: não expirou e a senha não mudou desde que ele foi gerado."""
    user_id = auth.link_token_user_id(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.active or not auth.link_token_matches(token, user.password_hash):
        return None
    return user


def set_password(db: Session, user: User, password: str) -> User:
    user.password_hash = passwords.hash_password(password)
    return _touch(db, user)


def send_access_email(user: User, link: str, invite: bool) -> bool:
    """Convite ou redefinição de senha por e-mail. False se o envio falhar (o admin ainda pode copiar o link)."""
    hours = INVITE_HOURS if invite else RESET_HOURS
    validity = f"{hours} horas" if hours > 1 else "1 hora"
    if invite:
        subject = "Seu acesso ao ImobiQ"
        lead = "Você recebeu acesso ao ImobiQ. Crie a sua senha para entrar:"
        action = "Criar minha senha"
        extra = "Se preferir, entre com a conta Google deste mesmo e-mail, sem criar senha."
    else:
        subject = "Redefinição de senha · ImobiQ"
        lead = "Recebemos um pedido para redefinir a sua senha do ImobiQ:"
        action = "Redefinir minha senha"
        extra = "Se não foi você, ignore este e-mail: a sua senha continua a mesma."
    content = EmailContent(
        subject=subject,
        text=f"{lead}\n\n{link}\n\nO link vale por {validity} e só pode ser usado uma vez.\n{extra}",
        html=(
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#1f2933">'
            '<p style="font-size:20px;font-weight:bold;margin:0 0 12px">Imobi<span style="color:#0f766e">Q</span></p>'
            f"<p>{escape(lead)}</p>"
            f'<p><a href="{escape(link)}" style="display:inline-block;background:#0f766e;color:#ffffff;'
            f'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:bold">{action}</a></p>'
            f'<p style="font-size:13px;color:#52606d">O link vale por {validity} e só pode ser usado uma vez.<br>'
            f"{escape(extra)}</p></div>"
        ),
    )
    try:
        mailer.deliver(mailer.build_message(content, user.name or user.email, user.email))
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("E-mail de acesso não enviado (%s)", type(exc).__name__)
        return False
