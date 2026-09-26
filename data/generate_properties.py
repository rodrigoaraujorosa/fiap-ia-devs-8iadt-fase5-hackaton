"""Gera a base simulada de imóveis COMERCIAIS (data/properties.json) de forma determinística.

Uso: python data/generate_properties.py

Tipos: sala comercial, conjunto comercial, laje corporativa, loja, galpão e prédio comercial, para locação ou
venda. Parte dos imóveis à venda já está locada (renda imediata para investidores).
Preços por m² são aproximações do mercado de São Paulo e região metropolitana, apenas para a POC.
"""

import json
import random
from pathlib import Path

random.seed(42)

# bairro: (zona, cidade, perfil, perto do metrô, referência curta para títulos)
PLACES = {
    # polos corporativos
    "Itaim Bibi": ("zona oeste", "São Paulo", "no eixo da Av. Brigadeiro Faria Lima, principal centro financeiro do país",
                   True, "na Faria Lima"),
    "Vila Olímpia": ("zona oeste", "São Paulo", "polo de tecnologia e startups, perto da Faria Lima e da Marginal Pinheiros",
                     True, "na Vila Olímpia"),
    "Pinheiros": ("zona oeste", "São Paulo", "entre a Faria Lima e a Linha 4-Amarela, cercado de restaurantes e serviços",
                  True, "em Pinheiros"),
    "Bela Vista": ("centro", "São Paulo", "a poucos passos da Av. Paulista, com metrô na porta", True, "na Paulista"),
    "Brooklin": ("zona sul", "São Paulo", "no eixo da Av. Engenheiro Luís Carlos Berrini, sede de multinacionais",
                 True, "na Berrini"),
    "Chácara Santo Antônio": ("zona sul", "São Paulo", "polo corporativo com prédios modernos e custo menor que a Berrini",
                              True, "na Chácara Santo Antônio"),
    "Barra Funda": ("zona oeste", "São Paulo", "região em transformação, com terminal intermodal e acesso às marginais",
                    True, "na Barra Funda"),
    "Alphaville": ("grande sp", "Barueri", "centro empresarial planejado, com acesso rápido à Rodovia Castello Branco",
                   False, "em Alphaville"),
    # bairros de serviços (salas e consultórios)
    "Moema": ("zona sul", "São Paulo", "bairro nobre com forte demanda por clínicas e consultórios", True, "em Moema"),
    "Vila Mariana": ("zona sul", "São Paulo", "polo de saúde e educação, com hospitais e universidades por perto", True,
                     "na Vila Mariana"),
    "Paraíso": ("zona sul", "São Paulo", "perto da Paulista e do complexo hospitalar da região", True, "no Paraíso"),
    "Tatuapé": ("zona leste", "São Paulo", "centro comercial mais valorizado da zona leste, com Linha 3-Vermelha", True,
                "no Tatuapé"),
    "Santana": ("zona norte", "São Paulo", "principal centro de comércio e serviços da zona norte, com metrô", True,
                "em Santana"),
    "Perdizes": ("zona oeste", "São Paulo", "região de consultórios e escritórios de advocacia, perto da PUC", False,
                 "em Perdizes"),
    "Santo Amaro": ("zona sul", "São Paulo", "centro comercial da zona sul, com trem, metrô e grande fluxo de pessoas",
                    True, "em Santo Amaro"),
    "República": ("centro", "São Paulo", "centro histórico com metrô, fluxo intenso e preços acessíveis", True,
                  "no Centro"),
    # ruas de varejo
    "Jardins": ("zona oeste", "São Paulo", "na Rua Oscar Freire, endereço das marcas de luxo", True, "na Oscar Freire"),
    "Consolação": ("centro", "São Paulo", "na Rua Augusta, com movimento de pedestres dia e noite", True, "na Augusta"),
    "Sé": ("centro", "São Paulo", "na região da Rua 25 de Março, maior centro de comércio popular do país", True,
           "na 25 de Março"),
    "Brás": ("centro", "São Paulo", "polo atacadista de moda, com compradores de todo o Brasil", True, "no Brás"),
    "Lapa": ("zona oeste", "São Paulo", "na Rua Doze de Outubro, comércio de rua tradicional e movimentado", True,
             "na Lapa"),
    # logística
    "Vila Leopoldina": ("zona oeste", "São Paulo", "ao lado da Marginal Pinheiros e do Ceagesp, ideal para last mile",
                        False, "na Vila Leopoldina"),
    "Mooca": ("zona leste", "São Paulo", "região industrial tradicional, perto do centro e da Radial Leste", False,
              "na Mooca"),
    "Jaguaré": ("zona oeste", "São Paulo", "entre a Marginal Pinheiros e o Rodoanel, ótimo para distribuição urbana",
                False, "no Jaguaré"),
    "Guarulhos": ("grande sp", "Guarulhos", "junto à Via Dutra e ao Aeroporto Internacional", False, "em Guarulhos"),
    "Cajamar": ("grande sp", "Cajamar", "maior polo logístico do país, na Rodovia Anhanguera", False, "em Cajamar"),
    "Osasco": ("grande sp", "Osasco", "com acesso direto à Castello Branco e ao Rodoanel", False, "em Osasco"),
}

# tipo: (bairros, faixa de área, cap rate % a.a. (retorno do aluguel sobre o preço), aluguel R$/m²/mês,
#        quantidade, fração à venda). O preço de venda sai do aluguel pelo cap rate, então tudo fica coerente.
TYPES = {
    "sala comercial": (["Moema", "Vila Mariana", "Paraíso", "Tatuapé", "Santana", "Perdizes", "Santo Amaro", "Pinheiros",
                        "Bela Vista", "República"], (28, 110), (6.5, 8.0), (55, 110), 25, 0.4),
    "conjunto comercial": (["Itaim Bibi", "Vila Olímpia", "Pinheiros", "Bela Vista", "Brooklin",
                            "Chácara Santo Antônio", "Barra Funda", "Alphaville", "Paraíso"], (120, 520),
                           (6.5, 8.0), (85, 170), 18, 0.35),
    "laje corporativa": (["Itaim Bibi", "Vila Olímpia", "Pinheiros", "Bela Vista", "Brooklin", "Chácara Santo Antônio",
                          "Alphaville"], (600, 2200), (6.3, 7.8), (100, 210), 12, 0.35),
    "loja": (["Jardins", "Consolação", "Sé", "Brás", "Tatuapé", "Santana", "Moema", "Pinheiros", "Lapa", "Vila Mariana",
              "Santo Amaro"], (40, 420), (7.0, 9.0), (75, 170), 22, 0.45),
    "galpão": (["Vila Leopoldina", "Mooca", "Jaguaré", "Santo Amaro", "Guarulhos", "Cajamar", "Osasco", "Barra Funda"],
               (900, 9000), (8.0, 9.5), (24, 40), 15, 0.4),
    "prédio comercial": (["República", "Vila Mariana", "Pinheiros", "Brooklin", "Santana", "Barra Funda"], (700, 4200),
                         (7.0, 9.0), (55, 100), 8, 0.6),
}

# ruas de luxo e de fluxo intenso valem mais (multiplicador sobre a faixa do tipo)
PREMIUM = {"Jardins": 2.2, "Sé": 1.8, "Itaim Bibi": 1.25, "Vila Olímpia": 1.1, "Brás": 1.4, "Consolação": 1.2,
           "Alphaville": 0.6, "Cajamar": 0.85, "República": 0.75, "Santana": 0.85}  # fmt: skip

ACTIVITIES = {
    "sala comercial": [["escritório", "consultório"], ["escritório", "consultório", "clínica"], ["escritório"]],
    "conjunto comercial": [["escritório"], ["escritório", "clínica"], ["escritório", "coworking"]],
    "laje corporativa": [["escritório"], ["escritório", "coworking"]],
    "loja": [["varejo", "serviços"], ["varejo", "alimentação"], ["varejo", "alimentação", "serviços"],
             ["varejo", "showroom"]],
    "galpão": [["logística", "armazenagem"], ["logística", "armazenagem", "e-commerce"],
               ["indústria leve", "armazenagem"]],
    "prédio comercial": [["escritório", "educação"], ["escritório", "clínica", "educação"], ["escritório", "coworking"]],
}

AMENITIES = {
    "office": ["recepção", "portaria 24h", "ar-condicionado central", "piso elevado", "forro modular", "gerador",
               "copa", "controle de acesso", "bicicletário e vestiários", "auditório compartilhado"],
    "premium_office": ["certificação LEED", "heliponto", "lajes sem pilares", "restaurante no prédio"],
    "loja": ["vitrine ampla", "mezanino", "alto fluxo de pedestres", "banheiro acessível", "depósito",
             "ponto de ônibus em frente", "estacionamento para clientes"],
    "galpão": ["docas niveladoras", "sprinklers", "pátio de manobras para carretas", "escritório administrativo",
               "vestiários", "portaria 24h", "cabine primária", "piso de alta resistência"],
    "prédio comercial": ["elevadores", "fachada ativa", "gerador", "estacionamento próprio", "retrofit recente",
                         "terraço", "auditório"],
}

# inquilinos dos imóveis à venda já locados, com a atividade que exercem (entra nas atividades permitidas)
TENANTS = {
    "sala comercial": {"clínica odontológica": "clínica", "escritório de contabilidade": "escritório",
                       "consultório de psicologia": "consultório"},
    "conjunto comercial": {"empresa de tecnologia": "escritório", "escritório de advocacia": "escritório",
                           "seguradora": "escritório"},
    "laje corporativa": {"banco digital": "escritório", "multinacional de bens de consumo": "escritório",
                         "consultoria": "escritório"},
    "loja": {"rede de farmácias": "varejo", "agência bancária": "serviços", "rede de cafeterias": "alimentação",
             "operadora de telefonia": "varejo"},
    "galpão": {"operador logístico": "logística", "e-commerce de moda": "e-commerce",
               "distribuidora de alimentos": "armazenagem"},
    "prédio comercial": {"faculdade": "educação", "rede de clínicas": "clínica", "empresa de call center": "escritório"},
}  # fmt: skip

DETAILS = {
    "sala comercial": "Sala pronta para uso, ideal para consultório, clínica ou escritório de pequeno porte.",
    "conjunto comercial": "Conjunto com planta flexível, fácil de adaptar para escritório aberto, salas de reunião "
    "ou clínica.",
    "laje corporativa": "Andar corporativo de alto padrão, com planta livre para até centenas de posições de trabalho.",
    "loja": "Loja de rua com boa visibilidade, pronta para varejo, alimentação ou serviços.",
    "galpão": "Galpão com estrutura para operações de armazenagem e distribuição, com fácil acesso de caminhões.",
    "prédio comercial": "Prédio inteiro para uso de uma única empresa (monousuário), com identidade própria na fachada.",
}


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def decimal(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}{suffix if n != 1 else ''}"


def round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def title_for(tipo: str, place: str, area: int, features: dict, leased: dict | None) -> str:
    ref = PLACES[place][4]
    if leased:
        noun = {"loja": "Loja locada", "galpão": "Galpão locado", "sala comercial": "Sala locada",
                "conjunto comercial": "Conjunto locado", "laje corporativa": "Laje locada",
                "prédio comercial": "Prédio locado"}[tipo]  # fmt: skip
        return f"{noun} para {leased['inquilino']} {ref}"
    options = {
        "sala comercial": [f"Sala comercial de {area} m² {ref}", f"Sala para consultório {ref}",
                           f"Sala comercial com vaga {ref}"],
        "conjunto comercial": [f"Conjunto comercial de {fmt_int(area)} m² {ref}", f"Conjunto corporativo {ref}"],
        "laje corporativa": [f"Laje corporativa de {fmt_int(area)} m² {ref}", f"Andar corporativo inteiro {ref}"],
        "loja": [f"Loja de rua {ref}", f"Ponto comercial {ref}", f"Loja com vitrine {ref}"],
        "galpão": [f"Galpão logístico de {fmt_int(area)} m² {ref}",
                   f"Galpão com {plural(features.get('docas', 2), 'doca')} {ref}"],
        "prédio comercial": [f"Prédio comercial de {features.get('andares', 4)} andares {ref}",
                             f"Edifício monousuário {ref}"],
    }[tipo]
    if tipo == "loja" and "esquina" in features.get("destaques", []):
        return f"Loja de esquina {ref}"
    return random.choice(options)


def build_property(idx: int, tipo: str, place: str, purpose: str, leased_sale: bool) -> dict:
    zone, city, profile, metro, _ = PLACES[place]
    _, (a_min, a_max), (cap_min, cap_max), (r_min, r_max), _, _ = TYPES[tipo]
    area = int(random.triangular(a_min, a_max, a_min + (a_max - a_min) * 0.25))
    area = round_to(area, 5 if area < 200 else 10 if area < 1000 else 50)
    mult = PREMIUM.get(place, 1.0)
    monthly_rent = area * random.uniform(r_min, r_max) * mult
    sale_price = monthly_rent * 12 / (random.uniform(cap_min, cap_max) / 100)

    features: dict = {"atividades": random.choice(ACTIVITIES[tipo])}
    highlights: list[str] = []
    if tipo in ("sala comercial", "conjunto comercial", "laje corporativa"):
        features["andar"] = random.randint(2, 24 if tipo == "laje corporativa" else 16)
        highlights = random.sample(AMENITIES["office"], 4)
        if tipo == "laje corporativa" and mult >= 1.0:
            highlights += random.sample(AMENITIES["premium_office"], 2)
        bathrooms = {"sala comercial": random.randint(1, 2), "conjunto comercial": random.randint(2, 6),
                     "laje corporativa": random.randint(6, 14)}[tipo]  # fmt: skip
        parking = max(0 if tipo == "sala comercial" else 2, round(area / random.uniform(35, 60)))
        condo = round_to(area * random.uniform(18, 34), 10)
    elif tipo == "loja":
        features["fachada_m"] = random.randint(4, 20)
        features["pe_direito_m"] = round(random.uniform(3.5, 7.0), 1)
        highlights = random.sample(AMENITIES["loja"], 3)
        if random.random() < 0.3:
            highlights.append("esquina")
        bathrooms = random.randint(1, 3)
        parking = random.choice([0, 0, 1, 2, 4])
        condo = None if random.random() < 0.7 else round_to(area * random.uniform(8, 18), 10)
    elif tipo == "galpão":
        features["pe_direito_m"] = round(random.uniform(8, 14), 1)
        features["docas"] = max(2, round(area / random.uniform(350, 700)))
        features["piso_carga_ton_m2"] = random.choice([3, 4, 5, 6, 8])
        features["acesso"] = {"Guarulhos": "Via Dutra", "Cajamar": "Rodovia Anhanguera", "Osasco": "Castello Branco",
                              "Jaguaré": "Rodoanel", "Vila Leopoldina": "Marginal Pinheiros",
                              "Mooca": "Radial Leste", "Santo Amaro": "Marginal Pinheiros",
                              "Barra Funda": "Marginal Tietê"}[place]  # fmt: skip
        highlights = random.sample(AMENITIES["galpão"], 4)
        bathrooms = random.randint(2, 8)
        parking = random.randint(10, 60)
        condo = round_to(area * random.uniform(3, 8), 10) if city != "São Paulo" else None
    else:  # prédio comercial
        features["andares"] = random.randint(3, 14)
        features["elevadores"] = max(1, features["andares"] // 4)
        highlights = random.sample(AMENITIES["prédio comercial"], 4)
        bathrooms = features["andares"] * 2
        parking = round(area / random.uniform(45, 80))
        condo = None
    features["destaques"] = highlights

    leased = None
    if purpose == "venda" and leased_sale:
        rent = round_to(monthly_rent * random.uniform(0.92, 1.05), 100)
        tenant = random.choice(list(TENANTS[tipo]))
        leased = {"inquilino": tenant, "contrato_ate": random.randint(2027, 2032), "aluguel_atual": rent}
        if TENANTS[tipo][tenant] not in features["atividades"]:
            features["atividades"] = [*features["atividades"], TENANTS[tipo][tenant]]
        features["locado"] = leased
        sale_price = rent * 12 / (random.uniform(cap_min, cap_max) / 100)  # vendido pelo cap rate
    rent_yield = monthly_rent * 12 / sale_price * 100
    if leased:
        rent_yield = leased["aluguel_atual"] * 12 / sale_price * 100

    furnished = tipo in ("sala comercial", "conjunto comercial", "laje corporativa") and random.random() < 0.25
    if furnished:
        highlights.append("mobiliado e pronto para uso")

    specs = [f"São {fmt_int(area)} m²"]
    if parking:
        specs.append(plural(parking, "vaga"))
    if "docas" in features:
        specs.append(f"{plural(features['docas'], 'doca')} e pé-direito de {decimal(features['pe_direito_m'])} m")
    elif "fachada_m" in features:
        specs.append(f"{features['fachada_m']} m de frente e pé-direito de {decimal(features['pe_direito_m'])} m")
    elif "andar" in features:
        specs.append(f"{features['andar']}º andar")
    elif "andares" in features:
        specs.append(f"{features['andares']} andares")
    parts = [
        random.choice([f"Localização estratégica em {place}: {profile}.", f"Excelente oportunidade em {place}: {profile}."]),
        DETAILS[tipo],
        ", ".join(specs) + ".",
        f"Permite: {', '.join(features['atividades'])}.",
    ]
    if leased:
        parts.append(
            f"Já locado para {leased['inquilino']}, contrato até {leased['contrato_ate']}, aluguel atual de "
            f"R$ {fmt_int(leased['aluguel_atual'])}/mês: renda desde o primeiro dia."
        )
    elif purpose == "venda":
        parts.append("Boa opção para sede própria ou para investir e alugar.")

    return {
        "id": f"IMV-{idx:03d}",
        "title": title_for(tipo, place, area, features, leased),
        "segment": "comercial",
        "property_type": tipo,
        "purpose": purpose,
        "neighborhood": place,
        "zone": zone,
        "city": city,
        "price": round_to(sale_price, 10000) if purpose == "venda" else round_to(monthly_rent, 100),
        "condo_fee": condo,
        "iptu": round_to(sale_price * 0.007 / 12, 10),
        "bedrooms": 0,
        "suites": 0,
        "bathrooms": bathrooms,
        "parking": parking,
        "area_m2": area,
        "description": " ".join(parts),
        "amenities": highlights,
        "features": {k: v for k, v in features.items() if k != "destaques"},
        "furnished": furnished,
        "pet_friendly": False,
        "accepts_financing": purpose == "venda" and random.random() < 0.8,
        "estimated_yield": round(rent_yield, 2) if purpose == "venda" else None,
        "near_metro": metro and random.random() < 0.85,
        "available": True,
    }


def main() -> None:
    properties = []
    idx = 1
    for tipo, (places, _, _, _, count, sale_share) in TYPES.items():
        for i in range(count):
            place = places[i % len(places)]
            purpose = "venda" if random.random() < sale_share else "aluguel"
            leased_sale = purpose == "venda" and random.random() < 0.55
            properties.append(build_property(idx, tipo, place, purpose, leased_sale))
            idx += 1

    out = Path(__file__).parent / "properties.json"
    out.write_text(json.dumps(properties, ensure_ascii=False, indent=2), encoding="utf-8")
    by_type: dict[str, int] = {}
    for p in properties:
        by_type[p["property_type"]] = by_type.get(p["property_type"], 0) + 1
    rent = sum(p["purpose"] == "aluguel" for p in properties)
    leased = sum("locado" in p["features"] for p in properties)
    print(f"{len(properties)} imóveis gerados em {out}: {by_type} · {rent} para alugar · {leased} locados à venda")


if __name__ == "__main__":
    main()
