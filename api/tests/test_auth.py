"""Login (senha e Google), papéis e o que cada um enxerga. Sem rede: o Google é simulado."""

import base64
import json
import time
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core import auth
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models import Appointment, Lead, User
from app.services import google_oauth, rate_limit, users

PASSWORD = "senha-da-demo"
APP = "http://localhost:3001"
OUTBOX: list = []  # e-mails que teriam sido enviados


@pytest.fixture
def secured(db, monkeypatch):
    """Login ligado (senha de administrador) e tabela de usuários vazia antes e depois."""
    monkeypatch.setattr(get_settings(), "admin_password", PASSWORD)
    monkeypatch.setattr(users.mailer, "deliver", lambda msg: OUTBOX.append(msg))  # nenhum e-mail sai nos testes
    OUTBOX.clear()
    rate_limit.reset()
    db.execute(delete(User))
    db.commit()
    yield db
    db.rollback()
    db.execute(delete(User))
    db.commit()
    rate_limit.reset()


@pytest.fixture
def browser(secured):
    """Um navegador novo por teste: o cookie de sessão não vaza para os outros testes."""
    return TestClient(app, follow_redirects=False)


def as_user(db, role: str, broker_id: int | None = None, email: str | None = None) -> dict:
    user = User(email=email or f"{role}@teste.dev", role=role, broker_id=broker_id)
    db.add(user)
    db.commit()
    return {"Authorization": f"Bearer {auth.issue_token(str(user.id))[0]}"}


def test_crm_requires_login(browser):
    lead_id = browser.post("/chat/sessions", json={}).json()["id"]  # o chat do visitante continua aberto
    try:
        for path in ("/leads", f"/leads/{lead_id}", "/appointments", "/dashboard/metrics", "/observability", "/users"):
            assert browser.get(path).status_code == 401, path
        assert browser.post(f"/leads/{lead_id}/summary").status_code == 401
        assert browser.get(f"/chat/{lead_id}/messages").status_code == 200
        # o chat retoma a conversa por uma rota própria do visitante, sem o que é interno do CRM
        state = browser.get(f"/chat/{lead_id}/state")
        assert state.status_code == 200 and state.json()["id"] == lead_id
        assert state.json()["summary"] is None and state.json()["emails"] == []
        assert browser.get("/auth/me").json() == {"required": True, "google": False, "password": True, "user": None}
    finally:
        with SessionLocal() as session:
            session.delete(session.get(Lead, lead_id))
            session.commit()


def test_password_login_opens_a_cookie_session(browser):
    assert browser.post("/auth/login", json={"password": "errada"}).status_code == 401
    response = browser.post("/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"]
    assert browser.get("/leads").status_code == 200  # o cookie basta, sem cabeçalho
    me = browser.get("/auth/me").json()["user"]
    assert me["role"] == "admin" and me["email"] is None
    assert browser.get("/config/ai").status_code == 200 and browser.get("/users").json() == []
    browser.post("/auth/logout")
    assert browser.get("/leads").status_code == 401


def test_roles_limit_what_each_user_reaches(browser, secured):
    gestor = as_user(secured, "gestor")
    viewer = as_user(secured, "visualizador")
    lead_id = secured.scalar(select(Lead.id).where(Lead.last_message_at.is_not(None)))

    assert browser.get("/leads", headers=gestor).status_code == 200
    assert browser.get("/observability", headers=gestor).status_code == 200
    assert browser.get("/config/ai", headers=gestor).status_code == 403
    assert browser.get("/users", headers=gestor).status_code == 403
    assert browser.post("/admin/demo/reset", headers=gestor).status_code == 403

    assert browser.get(f"/leads/{lead_id}", headers=viewer).status_code == 200
    assert browser.get("/observability", headers=viewer).status_code == 200
    assert browser.post(f"/leads/{lead_id}/summary", headers=viewer).status_code == 403  # só leitura
    assert browser.post(f"/leads/{lead_id}/summary/email", headers=viewer).status_code == 403


def test_broker_sees_only_own_leads_and_visits(browser, secured):
    visit = secured.scalars(select(Appointment)).first()
    broker_id = visit.broker_id
    corretor = as_user(secured, "corretor", broker_id=broker_id)
    unlinked = as_user(secured, "corretor", email="sem-vinculo@teste.dev")
    everyone = browser.get("/leads", headers=as_user(secured, "gestor")).json()

    mine = browser.get("/leads", headers=corretor).json()
    own = select(Appointment.lead_id).where(Appointment.broker_id == broker_id)
    expected = secured.scalars(
        select(Lead.id).where(
            Lead.last_message_at.is_not(None), (Lead.assigned_broker_id == broker_id) | Lead.id.in_(own)
        )
    ).all()
    assert mine and len(mine) < len(everyone)
    assert {lead["id"] for lead in mine} == {str(i) for i in expected}
    assert str(visit.lead_id) in {lead["id"] for lead in mine}
    other = next(lead["id"] for lead in everyone if lead["id"] not in {m["id"] for m in mine})
    assert browser.get(f"/leads/{visit.lead_id}", headers=corretor).status_code == 200
    assert browser.get(f"/leads/{other}", headers=corretor).status_code == 404  # nem confirma que existe
    assert browser.post(f"/leads/{other}/summary", headers=corretor).status_code == 404
    assert {a["broker"]["id"] for a in browser.get("/appointments?upcoming=false", headers=corretor).json()} == {
        broker_id
    }
    assert browser.get("/dashboard/metrics", headers=corretor).json()["total_leads"] == len(mine)
    assert browser.get("/observability", headers=corretor).status_code == 403

    assert browser.get("/leads", headers=unlinked).json() == []  # corretor sem vínculo não vê nada
    assert browser.get("/dashboard/metrics", headers=unlinked).json()["total_leads"] == 0


def test_admin_manages_users(browser, secured):
    admin = as_user(secured, "admin", email="chefe@teste.dev")
    broker_id = browser.get("/users/brokers", headers=admin).json()[0]["id"]

    created = browser.post("/users", headers=admin, json={"email": "Nova.Pessoa@Teste.dev", "role": "visualizador"})
    assert created.status_code == 201 and created.json()["email"] == "nova.pessoa@teste.dev"
    user_id = created.json()["id"]
    assert (
        browser.post("/users", headers=admin, json={"email": "nova.pessoa@teste.dev", "role": "gestor"}).status_code
        == 409
    )
    assert browser.post("/users", headers=admin, json={"email": "x@teste.dev", "role": "dono"}).status_code == 422

    linked = browser.patch(f"/users/{user_id}", headers=admin, json={"role": "corretor", "broker_id": broker_id}).json()
    assert linked["role"] == "corretor" and linked["broker_id"] == broker_id
    assert browser.patch(f"/users/{user_id}", headers=admin, json={"broker_id": 999999}).status_code == 422
    unlinked = browser.patch(f"/users/{user_id}", headers=admin, json={"role": "gestor"}).json()
    assert unlinked["broker_id"] is None  # o vínculo só existe para o papel corretor

    session = {"Authorization": f"Bearer {auth.issue_token(str(user_id))[0]}"}
    assert browser.get("/leads", headers=session).status_code == 200
    browser.patch(f"/users/{user_id}", headers=admin, json={"active": False})
    assert browser.get("/leads", headers=session).status_code == 401  # desativado perde o acesso na hora

    me = secured.scalar(select(User.id).where(User.email == "chefe@teste.dev"))
    assert browser.patch(f"/users/{me}", headers=admin, json={"active": False}).status_code == 400
    assert browser.patch(f"/users/{me}", headers=admin, json={"role": "gestor"}).status_code == 400
    assert browser.delete(f"/users/{me}", headers=admin).status_code == 400
    assert browser.delete(f"/users/{user_id}", headers=admin).status_code == 204
    assert [u["email"] for u in browser.get("/users", headers=admin).json()] == ["chefe@teste.dev"]


@pytest.fixture
def google(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "google_client_id", "cliente.apps.googleusercontent.com")
    monkeypatch.setattr(s, "google_client_secret", "segredo-de-teste")
    profile = {"email": "pessoa@teste.dev", "name": "Pessoa Teste", "picture": "https://foto.dev/p.png"}
    monkeypatch.setattr(google_oauth, "exchange", lambda code: dict(profile))
    return profile


def google_round_trip(browser, next_path: str = "/observability", tamper: bool = False) -> str:
    """Vai ao Google e volta; devolve o endereço para onde a API manda o navegador no fim."""
    start = browser.get(f"/auth/google/login?next={next_path}")
    assert start.status_code == 303 and start.headers["location"].startswith(google_oauth.AUTH_URL)
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["redirect_uri"] == ["http://localhost:8001/auth/google/callback"]
    state = "outro-state" if tamper else query["state"][0]
    back = browser.get(f"/auth/google/callback?code=abc&state={state}")
    assert back.status_code == 303
    return back.headers["location"]


def test_google_login_only_for_invited_users(browser, secured, google, monkeypatch):
    assert browser.get("/auth/me").json()["google"] is True

    assert google_round_trip(browser) == f"{APP}/observability?auth_error=nao_autorizado"  # sem convite
    assert browser.get("/leads").status_code == 401
    assert google_round_trip(browser, tamper=True) == f"{APP}/observability?auth_error=expirado"
    assert browser.get("/auth/google/callback?error=access_denied").headers["location"].endswith("auth_error=cancelado")

    secured.add(User(email="pessoa@teste.dev", role="visualizador"))
    secured.commit()
    assert google_round_trip(browser) == f"{APP}/observability"
    me = browser.get("/auth/me").json()["user"]
    assert me == {"name": "Pessoa Teste", "email": "pessoa@teste.dev", "picture": "https://foto.dev/p.png",
                  "role": "visualizador", "broker_id": None}  # fmt: skip
    assert browser.get("/leads").status_code == 200 and browser.get("/config/ai").status_code == 403

    browser.post("/auth/logout")
    secured.expire_all()
    secured.scalar(select(User)).active = False
    secured.commit()
    assert google_round_trip(browser).endswith("auth_error=nao_autorizado")  # desativado


def test_admin_emails_enter_without_invite(browser, secured, google, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_emails", "outra@teste.dev, Pessoa@Teste.dev")
    assert google_round_trip(browser, next_path="//site-malicioso.com") == f"{APP}/dashboard"  # só caminhos do app
    assert browser.get("/auth/me").json()["user"]["role"] == "admin"
    assert browser.get("/users").json()[0]["email"] == "pessoa@teste.dev"


def id_token(**claims) -> str:
    body = {
        "aud": "cliente.apps.googleusercontent.com",
        "iss": "https://accounts.google.com",
        "exp": time.time() + 600,
        "email": "Pessoa@Teste.dev",
        "email_verified": True,
        "name": "Pessoa",
        **claims,
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"cabecalho.{payload}.assinatura"


@pytest.mark.parametrize(
    ("claims", "ok"),
    [
        ({}, True),
        ({"aud": "outro-app"}, False),
        ({"iss": "https://impostor.dev"}, False),
        ({"exp": 1}, False),
        ({"email_verified": False}, False),
    ],
)
def test_id_token_is_validated(monkeypatch, claims, ok):
    s = get_settings()
    monkeypatch.setattr(s, "google_client_id", "cliente.apps.googleusercontent.com")
    monkeypatch.setattr(s, "google_client_secret", "segredo-de-teste")

    class Reply:
        status_code = 200

        def json(self):
            return {"id_token": id_token(**claims)}

    sent = {}

    def post(url, data, timeout):
        sent.update(data)
        return Reply()

    monkeypatch.setattr(google_oauth.httpx, "post", post)
    if ok:
        assert google_oauth.exchange("abc")["email"] == "pessoa@teste.dev"
        assert sent["grant_type"] == "authorization_code" and sent["code"] == "abc"
    else:
        with pytest.raises(google_oauth.GoogleAuthError):
            google_oauth.exchange("abc")


def link_token(link: str) -> str:
    assert link.startswith(f"{APP}/password?token=")
    return link.split("token=")[1]


def test_invited_user_creates_a_password_and_logs_in(browser, secured):
    admin = as_user(secured, "admin", email="chefe@teste.dev")
    invited = browser.post("/users", headers=admin, json={"email": "ana@teste.dev", "role": "gestor"}).json()
    assert invited["has_password"] is False and invited["access"]["emailed"] is True
    assert (
        OUTBOX[-1]["To"].endswith("<ana@teste.dev>")
        and invited["access"]["link"] in OUTBOX[-1].get_body().get_content()
    )
    token = link_token(invited["access"]["link"])

    assert browser.get(f"/auth/password?token={token}").json() == {
        "email": "ana@teste.dev",
        "name": None,
        "has_password": False,
        "needs_terms": True,
    }
    no_terms = browser.post("/auth/password", json={"token": token, "password": "senha-boa-123"})
    assert no_terms.status_code == 422 and "Termos" in no_terms.json()["detail"]  # sem o aceite, a conta não é criada
    new = {"token": token, "password": "senha-boa-123", "accept_terms": True}
    assert browser.post("/auth/password", json={**new, "password": "curta"}).status_code == 422
    assert browser.post("/auth/password", json={**new, "token": token + "x"}).status_code == 400
    assert browser.post("/auth/password", json=new).status_code == 200
    assert secured.scalar(select(User.terms_accepted_at).where(User.email == "ana@teste.dev")) is not None
    assert browser.get("/auth/me").json()["user"]["role"] == "gestor"  # definir a senha já abre a sessão
    assert browser.get(f"/auth/password?token={token}").status_code == 400  # o link vale uma vez só
    assert browser.post("/auth/password", json={"token": token, "password": "outra-senha-1"}).status_code == 400

    browser.post("/auth/logout")
    assert browser.post("/auth/login", json={"email": "ana@teste.dev", "password": "errada-123"}).status_code == 401
    assert (
        browser.post("/auth/login", json={"email": "ninguem@teste.dev", "password": "senha-boa-123"}).status_code == 401
    )
    ok = browser.post("/auth/login", json={"email": " Ana@Teste.dev ", "password": "senha-boa-123"})
    assert ok.status_code == 200 and "HttpOnly" in ok.headers["set-cookie"]
    assert browser.get("/leads").status_code == 200 and browser.get("/config/ai").status_code == 403
    stored = secured.scalar(select(User.password_hash).where(User.email == "ana@teste.dev"))
    assert stored.startswith("scrypt$") and "senha-boa-123" not in stored

    user_id = invited["id"]
    browser.post("/auth/logout")  # sem o cookie da Ana, vale o cabeçalho do admin
    assert browser.patch(f"/users/{user_id}", headers=admin, json={"active": False}).status_code == 200
    assert browser.post("/auth/login", json={"email": "ana@teste.dev", "password": "senha-boa-123"}).status_code == 401
    assert browser.post(f"/users/{user_id}/access-link", headers=admin).status_code == 404  # desativado


def test_forgot_password_sends_a_single_use_link(browser, secured):
    user = User(
        email="bia@teste.dev",
        role="visualizador",
        password_hash=users.passwords.hash_password("senha-antiga-1"),
        terms_accepted_at=datetime.now(UTC),
    )
    secured.add(user)
    secured.commit()

    assert browser.post("/auth/forgot", json={"email": "ninguem@teste.dev"}).json() == {"ok": True}
    assert OUTBOX == []  # mesma resposta, mas nada é enviado para quem não é usuário
    assert browser.post("/auth/forgot", json={"email": "Bia@Teste.dev"}).json() == {"ok": True}
    assert len(OUTBOX) == 1 and "Redefinição" in OUTBOX[0]["Subject"]
    body = OUTBOX[0].get_body(("plain",)).get_content()
    token = link_token(next(line for line in body.splitlines() if line.startswith(APP)))

    assert browser.get(f"/auth/password?token={token}").json()["needs_terms"] is False  # já aceitou ao criar a conta
    assert browser.post("/auth/password", json={"token": token, "password": "senha-nova-456"}).status_code == 200
    browser.post("/auth/logout")
    assert browser.post("/auth/login", json={"email": "bia@teste.dev", "password": "senha-antiga-1"}).status_code == 401
    assert browser.post("/auth/login", json={"email": "bia@teste.dev", "password": "senha-nova-456"}).status_code == 200

    for _ in range(5):  # no máximo 3 e-mails de redefinição por hora para o mesmo endereço
        browser.post("/auth/forgot", json={"email": "bia@teste.dev"})
    assert len(OUTBOX) == 3


def test_login_attempts_are_limited(browser, secured, monkeypatch):
    async def no_wait(seconds):
        return None

    monkeypatch.setattr("app.api.routes.auth.asyncio.sleep", no_wait)
    attempt = {"email": "alvo@teste.dev", "password": "chute-qualquer"}
    assert [browser.post("/auth/login", json=attempt).status_code for _ in range(11)] == [401] * 10 + [429]
    assert browser.post("/auth/login", json={"email": "outra@teste.dev", "password": "x"}).status_code == 401
