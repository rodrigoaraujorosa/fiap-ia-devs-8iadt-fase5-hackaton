from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.session import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # ex.: IMV-001
    title: Mapped[str] = mapped_column(String(200))
    property_type: Mapped[str] = mapped_column(String(40), index=True)  # apartamento, casa, studio...
    purpose: Mapped[str] = mapped_column(String(20), index=True)  # venda | aluguel
    neighborhood: Mapped[str] = mapped_column(String(80), index=True)
    zone: Mapped[str] = mapped_column(String(40), index=True)  # zona sul, zona oeste...
    city: Mapped[str] = mapped_column(String(80), default="São Paulo")

    price: Mapped[int] = mapped_column(Integer, index=True)  # venda: valor total | aluguel: mensal
    condo_fee: Mapped[int | None] = mapped_column(Integer)
    iptu: Mapped[int | None] = mapped_column(Integer)  # mensal
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    suites: Mapped[int] = mapped_column(Integer, default=0)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1)
    parking: Mapped[int] = mapped_column(Integer, default=0)
    area_m2: Mapped[int] = mapped_column(Integer)

    description: Mapped[str] = mapped_column(Text)
    amenities: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    furnished: Mapped[bool] = mapped_column(Boolean, default=False)
    pet_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_financing: Mapped[bool] = mapped_column(Boolean, default=True)
    estimated_yield: Mapped[float | None] = mapped_column(Float)  # % a.a. (aluguel/preço)
    near_metro: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    embedding = mapped_column(Vector(get_settings().embedding_dim), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def search_text(self) -> str:
        """Texto usado para gerar o embedding (RAG)."""
        finalidade = "à venda" if self.purpose == "venda" else "para alugar"
        extras = [
            "mobiliado" if self.furnished else None,
            "aceita pet" if self.pet_friendly else None,
            "próximo ao metrô" if self.near_metro else None,
        ]
        return (
            f"{self.title}. {self.property_type} {finalidade} em {self.neighborhood}, "
            f"{self.zone}, {self.city}. {self.bedrooms} quartos, {self.area_m2} m². "
            f"{self.description} Comodidades: {', '.join(self.amenities)}. "
            f"{', '.join(e for e in extras if e)}"
        )
