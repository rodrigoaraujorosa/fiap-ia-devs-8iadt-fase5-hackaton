"""Login com Google (OpenID Connect, fluxo "authorization code", feito no servidor).

O navegador vai ao Google e volta com um código; a API troca o código pelo id_token direto com o Google, por
HTTPS e com o client secret. Como o token vem dessa conexão autenticada, e não do navegador, a especificação
dispensa conferir a assinatura dele: basta validar para quem foi emitido, por quem, a validade e o e-mail.
"""

import base64
import json
import time
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


class GoogleAuthError(Exception):
    """Login recusado (a mensagem nunca inclui segredos nem o token)."""


def redirect_uri() -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/auth/google/callback"


def authorization_url(state: str) -> str:
    params = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise GoogleAuthError("Resposta do Google em formato inesperado") from exc


def exchange(code: str) -> dict:
    """Troca o código pelo id_token e devolve os dados validados: email, name e picture."""
    s = get_settings()
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise GoogleAuthError(f"Google indisponível: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise GoogleAuthError(f"O Google recusou o código ({response.status_code})")
    claims = _claims(response.json().get("id_token", ""))
    if claims.get("aud") != s.google_client_id or claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("Token emitido para outro aplicativo")
    if int(claims.get("exp", 0)) < time.time():
        raise GoogleAuthError("Token expirado")
    if not claims.get("email") or claims.get("email_verified") not in (True, "true"):
        raise GoogleAuthError("Conta Google sem e-mail verificado")
    return {"email": claims["email"].lower(), "name": claims.get("name"), "picture": claims.get("picture")}
