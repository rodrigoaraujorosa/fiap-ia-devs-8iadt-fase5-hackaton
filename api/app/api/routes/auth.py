import asyncio

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.auth import admin_required, bearer, check_password, issue_token, token_valid

router = APIRouter(prefix="/auth", tags=["acesso"])


class LoginIn(BaseModel):
    password: str


@router.get("/status")
def auth_status(authorization: str | None = Header(None)):
    """Se a área de administração exige senha e se o token enviado ainda vale."""
    return {"required": admin_required(), "authenticated": token_valid(bearer(authorization))}


@router.post("/login")
async def login(payload: LoginIn):
    """Troca a senha de administrador (ADMIN_PASSWORD no .env) por um token válido por 12 horas."""
    if not admin_required():
        raise HTTPException(404, "Área de administração sem senha configurada")
    if not check_password(payload.password):
        await asyncio.sleep(1)  # atrasa tentativas de adivinhar a senha
        raise HTTPException(401, "Senha incorreta")
    token, expires_at = issue_token()
    return {"token": token, "expires_at": expires_at}
