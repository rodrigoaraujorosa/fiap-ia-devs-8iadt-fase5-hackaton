from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import UserRole


class User(Base):
    """Quem pode entrar no ImobiQ, com e-mail e senha ou com a conta Google do mesmo e-mail.

    Só entra quem está nesta tabela (convidado por um admin). A senha é opcional: quem usa só o Google não tem.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)  # sempre em minúsculas
    name: Mapped[str | None] = mapped_column(String(120))  # preenchido pelo Google no primeiro login
    picture: Mapped[str | None] = mapped_column(String(400))
    password_hash: Mapped[str | None] = mapped_column(String(200))  # scrypt; nunca a senha em si
    role: Mapped[str] = mapped_column(String(20), default=UserRole.VISUALIZADOR)
    # corretor da base que este usuário representa: o papel "corretor" só vê os leads e visitas dele
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id", ondelete="SET NULL"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # quando a pessoa marcou que leu e aceita os Termos de Uso e a Política de Privacidade (ao criar a senha)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    broker: Mapped["Broker | None"] = relationship()  # noqa: F821

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)
