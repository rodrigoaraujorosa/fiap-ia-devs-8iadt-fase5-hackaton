from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require_admin
from app.db.session import get_db
from app.models import Broker, User
from app.models.enums import UserRole
from app.services import users

router = APIRouter(tags=["usuários"], dependencies=[Depends(require_admin)])

Role = Literal["admin", "gestor", "corretor", "visualizador"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    picture: str | None
    role: str
    broker_id: int | None
    active: bool
    has_password: bool
    created_at: datetime
    last_login_at: datetime | None


class AccessLink(BaseModel):
    link: str  # a pessoa abre, cria a senha e já entra; vale 72 horas e uma vez só
    emailed: bool  # o convite também foi por e-mail?


class InvitedUser(UserOut):
    access: AccessLink


class UserIn(BaseModel):
    email: EmailStr
    role: Role
    broker_id: int | None = None


class UserPatch(BaseModel):
    role: Role | None = None
    broker_id: int | None = None
    active: bool | None = None


class BrokerOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str


def _check_broker(db: Session, role: str, broker_id: int | None) -> int | None:
    """Só o papel corretor fica vinculado a um corretor da base."""
    if role != UserRole.CORRETOR:
        return None
    if broker_id is not None and db.get(Broker, broker_id) is None:
        raise HTTPException(422, "Corretor não encontrado")
    return broker_id


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.active.desc(), User.email)).all()


@router.get("/users/brokers", response_model=list[BrokerOption])
def list_brokers(db: Session = Depends(get_db)):
    """Corretores da base, para vincular a um usuário com o papel corretor."""
    return db.scalars(select(Broker).where(Broker.active).order_by(Broker.name)).all()


def _access(user: User) -> dict:
    link = users.access_link(user, users.INVITE_HOURS)
    return {"link": link, "emailed": users.send_access_email(user, link, invite=not user.has_password)}


@router.post("/users", response_model=InvitedUser, status_code=201)
def invite_user(payload: UserIn, db: Session = Depends(get_db)):
    """Convida um e-mail com um papel. A pessoa recebe o link para criar a senha (e pode entrar com o Google)."""
    email = payload.email.strip().lower()
    if users.by_email(db, email):
        raise HTTPException(409, "Este e-mail já está cadastrado")
    user = User(email=email, role=payload.role, broker_id=_check_broker(db, payload.role, payload.broker_id))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {**UserOut.model_validate(user).model_dump(), "access": _access(user)}


@router.post("/users/{user_id}/access-link", response_model=AccessLink)
def new_access_link(user_id: int, db: Session = Depends(get_db)):
    """Gera (e envia por e-mail) um novo link para a pessoa criar ou redefinir a senha."""
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(404, "Usuário não encontrado ou desativado")
    return _access(user)


def _own(db: Session, user_id: int, principal: Principal, action: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado")
    if principal.user_id == user.id:
        raise HTTPException(400, f"Você não pode {action} o seu próprio usuário")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserPatch, principal: Principal = Depends(require_admin),
                db: Session = Depends(get_db)):  # fmt: skip
    """Troca o papel, o corretor vinculado ou desativa. Vale na próxima requisição do usuário."""
    changes = payload.model_dump(exclude_unset=True)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado")
    if principal.user_id == user.id and (changes.get("active") is False or changes.get("role", user.role) != user.role):
        raise HTTPException(400, "Você não pode rebaixar nem desativar o seu próprio usuário")
    if "role" in changes and changes["role"]:
        user.role = changes["role"]
    if "active" in changes and changes["active"] is not None:
        user.active = changes["active"]
    broker_id = changes["broker_id"] if "broker_id" in changes else user.broker_id
    user.broker_id = _check_broker(db, user.role, broker_id)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(_own(db, user_id, principal, "excluir"))
    db.commit()
