"""Gera a base simulada de imóveis (data/properties.json) de forma determinística.

Uso: python data/generate_properties.py
Os preços por m² são aproximações de mercado de São Paulo, apenas para a POC.
"""

import json
import random
from pathlib import Path

random.seed(42)

# bairro: (zona, preço médio de venda por m², perfil do bairro, perto do metrô)
NEIGHBORHOODS = {
    "Moema": ("zona sul", 16500, "bairro nobre e arborizado, a poucos minutos do Parque Ibirapuera", True),
    "Vila Mariana": ("zona sul", 13500, "bairro tradicional com ótima oferta de metrô, escolas e universidades", True),
    "Brooklin": ("zona sul", 14000, "região valorizada, próxima à Av. Berrini e aos polos empresariais", True),
    "Campo Belo": ("zona sul", 13000, "bairro residencial tranquilo, perto do Aeroporto de Congonhas", True),
    "Saúde": ("zona sul", 11500, "bairro familiar com comércio de rua forte e acesso à Linha 1-Azul", True),
    "Santo Amaro": ("zona sul", 9000, "centro comercial da zona sul, com excelente infraestrutura e custo acessível", True),
    "Pinheiros": ("zona oeste", 17500, "bairro vibrante, com gastronomia, vida noturna e Linha 4-Amarela", True),
    "Vila Madalena": ("zona oeste", 15500, "bairro boêmio e criativo, cheio de bares, galerias e ateliês", True),
    "Perdizes": ("zona oeste", 13500, "bairro residencial de ruas arborizadas, próximo à PUC e ao Allianz Parque", False),
    "Butantã": ("zona oeste", 9500, "região próxima à USP, com bom custo-benefício e crescimento acelerado", True),
    "Lapa": ("zona oeste", 10500, "bairro em transformação, com trem, metrô próximo e muitos lançamentos", True),
    "Santana": ("zona norte", 10000, "principal bairro da zona norte, com shopping, metrô e comércio completo", True),
    "Tucuruvi": ("zona norte", 8500, "bairro residencial, final da Linha 1-Azul, com preços acessíveis", True),
    "Casa Verde": ("zona norte", 7500, "bairro tranquilo e familiar, com casas amplas e bom acesso à marginal", False),
    "Tatuapé": ("zona leste", 10500, "bairro mais valorizado da zona leste, com shoppings e Linha 3-Vermelha", True),
    "Mooca": ("zona leste", 9500, "bairro tradicional de origem italiana, com muitos lançamentos residenciais", True),
    "Vila Prudente": ("zona leste", 8500, "bairro com metrô e monotrilho, ótimo para quem busca primeiro imóvel", True),
    "Bela Vista": ("centro", 10500, "bairro central, a passos da Av. Paulista, ideal para quem quer andar a pé", True),
    "Consolação": ("centro", 12500, "região central valorizada, próxima à Paulista e à Rua Augusta", True),
    "República": ("centro", 8000, "centro histórico com muitos studios, alta demanda de locação", True),
}

# tipo: (faixa de área m², quartos possíveis, fator de preço por m²)
TYPES = {
    "studio": ((22, 38), [0], 1.15),
    "apartamento": ((45, 140), [1, 2, 2, 3, 3, 4], 1.0),
    "cobertura": ((120, 260), [3, 4], 1.2),
    "casa": ((110, 320), [2, 3, 3, 4], 0.85),
    "sala comercial": ((30, 90), [0], 0.9),
}

AMENITIES_CONDO = ["piscina", "academia", "salão de festas", "churrasqueira", "playground", "portaria 24h",
                   "coworking", "lavanderia coletiva", "espaço gourmet", "quadra poliesportiva", "bicicletário",
                   "pet place", "sauna"]
AMENITIES_UNIT = ["varanda gourmet", "ar-condicionado", "armários planejados", "piso de madeira",
                  "cozinha americana", "vista livre", "andar alto", "sol da manhã", "depósito privativo"]
AMENITIES_HOUSE = ["quintal", "edícula", "jardim", "churrasqueira", "área de serviço ampla", "lareira"]
AMENITIES_OFFICE = ["recepção", "ar-condicionado central", "piso elevado", "copa", "portaria 24h"]

TITLE_TEMPLATES = {
    "studio": ["Studio moderno em {b}", "Studio compacto e funcional em {b}", "Studio bem planejado em {b}"],
    "apartamento": ["Apartamento de {q} em {b}", "Apartamento amplo em {b}", "Apartamento com varanda em {b}",
                    "Apartamento reformado em {b}"],
    "cobertura": ["Cobertura duplex em {b}", "Cobertura com terraço em {b}"],
    "casa": ["Casa de {q} em {b}", "Sobrado em {b}", "Casa térrea com quintal em {b}"],
    "sala comercial": ["Sala comercial em {b}", "Conjunto comercial em {b}"],
}

DESC_OPENERS = [
    "Imóvel muito bem localizado, {perfil}.",
    "Excelente oportunidade em {bairro}: {perfil}.",
    "Localização privilegiada — {perfil}.",
    "Para quem busca qualidade de vida: {perfil}.",
]
DESC_DETAILS = {
    "studio": "Planta inteligente, ideal para quem mora sozinho ou para investidores que buscam renda com locação.",
    "apartamento": "Ambientes integrados, boa iluminação natural e planta que aproveita bem cada metro quadrado.",
    "cobertura": "Área externa ampla com terraço, perfeita para receber amigos, e acabamento de alto padrão.",
    "casa": "Casa espaçosa, com privacidade e área externa — ideal para famílias e para quem tem pets.",
    "sala comercial": "Pronta para uso, em prédio corporativo com boa infraestrutura para escritórios e clínicas.",
}
INVEST_HINTS = [
    "Alta procura para locação na região.",
    "Região com forte valorização nos últimos anos.",
    "Ótimo para renda com aluguel de curta ou longa temporada.",
]


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("s" if n != 1 else "")


def round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def build_property(idx: int, bairro: str, tipo: str, finalidade: str) -> dict:
    zona, m2_price, perfil, metro = NEIGHBORHOODS[bairro]
    (a_min, a_max), quartos_opts, fator = TYPES[tipo]
    area = int(random.triangular(a_min, a_max, a_min + (a_max - a_min) * 0.2))  # mais imóveis compactos
    quartos = random.choice(quartos_opts)
    if tipo == "apartamento":  # área coerente com a quantidade de quartos
        area = max(area, 30 + quartos * 22)
    suites = 0 if quartos == 0 else random.randint(0 if quartos < 2 else 1, max(1, quartos - 1))
    banheiros = max(1, suites + random.randint(0, 1))
    vagas = 0 if tipo in ("studio",) and random.random() < 0.6 else random.randint(1, max(1, quartos))

    sale_price = area * m2_price * fator * random.uniform(0.88, 1.12)
    rent_yield = random.uniform(4.2, 6.8) if tipo != "sala comercial" else random.uniform(6.0, 8.0)
    if tipo == "studio":
        rent_yield += 0.8  # studios costumam render mais
    monthly_rent = sale_price * rent_yield / 100 / 12

    is_house = tipo == "casa"
    if tipo == "sala comercial":
        amenities = random.sample(AMENITIES_OFFICE, 3)
    elif is_house:
        amenities = random.sample(AMENITIES_HOUSE, 3) + random.sample(AMENITIES_UNIT[:5], 1)
    else:
        amenities = random.sample(AMENITIES_CONDO, random.randint(3, 6)) + random.sample(AMENITIES_UNIT, 2)

    furnished = tipo == "studio" and random.random() < 0.6 or finalidade == "aluguel" and random.random() < 0.25
    pet = is_house or "pet place" in amenities or random.random() < 0.5
    condo = 0 if is_house else round_to(area * random.uniform(9, 16), 10)
    iptu = round_to(sale_price * 0.006 / 12, 10)

    desc = " ".join([
        random.choice(DESC_OPENERS).format(perfil=perfil, bairro=bairro),
        DESC_DETAILS[tipo],
        f"São {area} m²" + (f", {plural(quartos, 'quarto')}" if quartos else "")
        + (f" (sendo {plural(suites, 'suíte')})" if suites else "") + f" e {plural(vagas, 'vaga') if vagas else 'sem vaga de garagem'}.",
        random.choice(INVEST_HINTS) if finalidade == "venda" and tipo in ("studio", "sala comercial", "apartamento") else "",
    ]).strip()

    title = random.choice(TITLE_TEMPLATES[tipo]).format(b=bairro, q=plural(quartos, "quarto"))
    if furnished and tipo == "studio":
        title = title.replace("Studio", "Studio mobiliado", 1)

    return {
        "id": f"IMV-{idx:03d}",
        "title": title,
        "property_type": tipo,
        "purpose": finalidade,
        "neighborhood": bairro,
        "zone": zona,
        "city": "São Paulo",
        "price": round_to(sale_price, 5000) if finalidade == "venda" else round_to(monthly_rent, 50),
        "condo_fee": condo or None,
        "iptu": iptu,
        "bedrooms": quartos,
        "suites": suites,
        "bathrooms": banheiros,
        "parking": vagas,
        "area_m2": area,
        "description": desc,
        "amenities": amenities,
        "furnished": furnished,
        "pet_friendly": pet,
        "accepts_financing": finalidade == "venda" and random.random() < 0.9,
        "estimated_yield": round(rent_yield, 2) if finalidade == "venda" else None,
        "near_metro": metro and random.random() < 0.85,
        "available": True,
    }


def main() -> None:
    type_weights = {"apartamento": 0.5, "studio": 0.18, "casa": 0.15, "cobertura": 0.07, "sala comercial": 0.10}
    properties = []
    idx = 1
    bairros = list(NEIGHBORHOODS)
    # 5 imóveis por bairro (100 no total): 3 à venda e 2 para aluguel
    for bairro in bairros:
        for i in range(5):
            tipo = random.choices(list(type_weights), weights=list(type_weights.values()))[0]
            if NEIGHBORHOODS[bairro][1] < 9000 and tipo == "cobertura":
                tipo = "apartamento"
            finalidade = "venda" if i < 3 else "aluguel"
            properties.append(build_property(idx, bairro, tipo, finalidade))
            idx += 1

    out = Path(__file__).parent / "properties.json"
    out.write_text(json.dumps(properties, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(properties)} imóveis gerados em {out}")


if __name__ == "__main__":
    main()
