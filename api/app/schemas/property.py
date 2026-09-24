from pydantic import BaseModel, ConfigDict, Field


class PropertySearchParams(BaseModel):
    """Filtros de busca — também serão os argumentos da tool `buscar_imoveis` do agente."""

    query: str | None = Field(None, description="Descrição livre do que o cliente procura (busca semântica)")
    purpose: str | None = Field(None, description="'venda' ou 'aluguel'")
    property_type: str | None = Field(None, description="apartamento, casa, studio, cobertura, sala comercial")
    zones: list[str] | None = Field(None, description="Ex.: ['zona sul', 'zona oeste']")
    neighborhoods: list[str] | None = Field(None, description="Ex.: ['Moema', 'Vila Mariana']")
    min_price: int | None = None
    max_price: int | None = None
    min_bedrooms: int | None = None
    pet_friendly: bool | None = None
    furnished: bool | None = None
    min_yield: float | None = Field(None, description="Rentabilidade mínima estimada (% a.a.)")
    limit: int = Field(5, ge=1, le=20)


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    property_type: str
    purpose: str
    neighborhood: str
    zone: str
    city: str
    price: int
    condo_fee: int | None
    iptu: int | None
    bedrooms: int
    suites: int
    bathrooms: int
    parking: int
    area_m2: int
    description: str
    amenities: list[str]
    furnished: bool
    pet_friendly: bool
    accepts_financing: bool
    estimated_yield: float | None
    near_metro: bool
    available: bool


class PropertySearchResult(PropertyOut):
    similarity: float | None = None
