from pydantic import BaseModel, ConfigDict, Field


class PropertySearchParams(BaseModel):
    """Filtros de busca — também são os argumentos da tool `buscar_imoveis` do agente."""

    query: str | None = Field(None, description="Descrição livre do que o cliente procura (busca semântica)")
    purpose: str | None = Field(None, description="'venda' ou 'aluguel'")
    segment: str | None = Field(None, description="'comercial' ou 'residencial'")
    property_type: str | None = Field(
        None,
        description="Comercial: conjunto comercial, andar corporativo, laje corporativa, prédio comercial, galpão "
        "(sinônimos como 'escritório', 'sala', 'sede', 'depósito', 'CD' também funcionam). "
        "Residencial: apartamento, cobertura, casa, studio",
    )
    zones: list[str] | None = Field(None, description="Ex.: ['zona sul', 'zona oeste', 'centro', 'grande sp']")
    neighborhoods: list[str] | None = Field(None, description="Ex.: ['Itaim Bibi', 'Vila Olímpia']")
    min_price: int | None = None
    max_price: int | None = None
    min_area: int | None = Field(None, description="Área mínima em m²")
    max_area: int | None = Field(None, description="Área máxima em m²")
    min_parking: int | None = Field(None, description="Vagas de garagem mínimas")
    activity: str | None = Field(
        None,
        description="Atividade que o imóvel precisa permitir: escritório, consultório, clínica, coworking, varejo, "
        "alimentação, serviços, showroom, logística, armazenagem, e-commerce, indústria leve, educação",
    )
    min_docks: int | None = Field(None, description="Galpões: docas mínimas")
    min_ceiling_height: float | None = Field(None, description="Pé-direito mínimo em metros (galpões)")
    leased: bool | None = Field(None, description="True: só imóveis à venda já locados (renda imediata p/ investidor)")
    furnished: bool | None = Field(None, description="Mobiliado/pronto para uso")
    min_yield: float | None = Field(None, description="Rentabilidade mínima estimada (% a.a.)")
    min_bedrooms: int | None = Field(None, description="Só residencial: quartos mínimos")
    pet_friendly: bool | None = Field(None, description="Só residencial")
    limit: int = Field(5, ge=1, le=20)


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    segment: str
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
    features: dict
    furnished: bool
    pet_friendly: bool
    accepts_financing: bool
    estimated_yield: float | None
    near_metro: bool
    available: bool


class PropertySearchResult(PropertyOut):
    similarity: float | None = None
