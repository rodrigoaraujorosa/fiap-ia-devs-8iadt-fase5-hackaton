"""Gera a base simulada de imóveis (data/properties.json) de forma determinística.

Uso: python data/generate_properties.py

Carteira inspirada no perfil das imobiliárias de "real estate" corporativo de São Paulo: conjuntos, andares
corporativos, lajes (core & shell), prédios inteiros e galpões logísticos, para locação ou venda. Parte dos
imóveis à venda já está locada (renda imediata para investidores). Há também alguns residenciais de alto padrão à
venda, como nessas carteiras, o que mostra que o agente atende os dois segmentos.
Nomes de edifícios e condomínios são fictícios. Preços por m² são aproximações do mercado, apenas para a POC.
"""

import json
import random
from pathlib import Path

random.seed(74)  # semente escolhida para a base cobrir os cenários da demo

# bairro: (zona, cidade, perfil, perto do metrô, referência curta para títulos)
PLACES = {
    # polos corporativos
    "Itaim Bibi": ("zona oeste", "São Paulo", "no eixo da Av. Brigadeiro Faria Lima e da Av. Juscelino Kubitschek, "
                   "principal centro financeiro do país", True, "na Faria Lima"),
    "Jardim Europa": ("zona oeste", "São Paulo", "na Faria Lima, junto ao Jardim Europa, endereço de gestoras e "
                      "family offices", True, "no Jardim Europa"),
    "Vila Olímpia": ("zona oeste", "São Paulo", "polo de tecnologia e multinacionais, perto da JK e da Marginal "
                     "Pinheiros", True, "na Vila Olímpia"),
    "Pinheiros": ("zona oeste", "São Paulo", "entre a Faria Lima e a Linha 4-Amarela, cercado de restaurantes e "
                  "serviços", True, "em Pinheiros"),
    "Vila Madalena": ("zona oeste", "São Paulo", "bairro criativo, preferido por agências e empresas de tecnologia",
                      True, "na Vila Madalena"),
    "Brooklin": ("zona sul", "São Paulo", "no eixo da Av. Engenheiro Luís Carlos Berrini, sede de multinacionais",
                 True, "na Berrini"),
    "Cidade Monções": ("zona sul", "São Paulo", "entre a Berrini e a Marginal Pinheiros, com torres corporativas "
                       "recentes", True, "na Cidade Monções"),
    "Chácara Santo Antônio": ("zona sul", "São Paulo", "na Av. Chucri Zaidan, polo de torres corporativas modernas "
                              "com custo menor que a Faria Lima", True, "na Chácara Santo Antônio"),
    "Bela Vista": ("centro", "São Paulo", "a poucos passos da Av. Paulista, com metrô na porta", True, "na Paulista"),
    "Cerqueira César": ("zona oeste", "São Paulo", "no lado dos Jardins da Av. Paulista, perto de hospitais e "
                        "consulados", True, "na Paulista"),
    "Jardins": ("zona oeste", "São Paulo", "entre a Paulista e a Av. Brasil, endereço nobre e arborizado", True,
                "nos Jardins"),
    "Paraíso": ("zona sul", "São Paulo", "perto da Paulista e do complexo hospitalar da região", True, "no Paraíso"),
    "Vila Mariana": ("zona sul", "São Paulo", "polo de saúde e educação, com hospitais e universidades por perto",
                     True, "na Vila Mariana"),
    "Moema": ("zona sul", "São Paulo", "bairro nobre, com forte demanda por clínicas e consultórios", True,
              "em Moema"),
    "Liberdade": ("centro", "São Paulo", "ao lado do centro e da Paulista, com metrô e acesso fácil", True,
                  "na Liberdade"),
    "Barra Funda": ("zona oeste", "São Paulo", "região em transformação, com terminal intermodal e acesso às "
                    "marginais", True, "na Barra Funda"),
    "Vila Leopoldina": ("zona oeste", "São Paulo", "ao lado da Marginal Pinheiros, com escritórios novos e galpões "
                        "de última milha", False, "na Vila Leopoldina"),
    "Alphaville": ("grande sp", "Barueri", "centro empresarial planejado, com acesso rápido à Rodovia Castello "
                   "Branco", False, "em Alphaville"),
    # logística
    "Jaguaré": ("zona oeste", "São Paulo", "entre a Marginal Pinheiros e o Rodoanel, ótimo para distribuição urbana",
                False, "no Jaguaré"),
    "Guarulhos": ("grande sp", "Guarulhos", "junto à Via Dutra e ao Aeroporto Internacional", False, "em Guarulhos"),
    "Cajamar": ("grande sp", "Cajamar", "maior polo logístico do país, na Rodovia Anhanguera", False, "em Cajamar"),
    "Itapevi": ("grande sp", "Itapevi", "com acesso direto à Castello Branco e ao Rodoanel", False, "em Itapevi"),
    "Embu das Artes": ("grande sp", "Embu das Artes", "às margens da Régis Bittencourt e do Rodoanel", False,
                       "em Embu das Artes"),
    "Jundiaí": ("interior", "Jundiaí", "entre a Anhanguera e a Bandeirantes, a 50 km da capital", False,
                "em Jundiaí"),
    "Araçariguama": ("interior", "Araçariguama", "na Castello Branco, com terrenos amplos e custo competitivo",
                     False, "em Araçariguama"),
    "Extrema": ("interior", "Extrema", "na Rodovia Fernão Dias, já em Minas Gerais, com incentivos fiscais", False,
                "em Extrema (MG)"),
    # residencial de alto padrão
    "Vila Nova Conceição": ("zona sul", "São Paulo", "ao lado do Parque Ibirapuera, um dos metros quadrados mais "
                            "valorizados do país", False, "na Vila Nova Conceição"),
    "Cidade Jardim": ("zona oeste", "São Paulo", "bairro residencial exclusivo, perto da Marginal e do Jockey", False,
                      "na Cidade Jardim"),
    "Alto de Pinheiros": ("zona oeste", "São Paulo", "ruas arborizadas e tranquilas, perto da Praça Pan-Americana",
                          False, "no Alto de Pinheiros"),
    "Jardim Guedala": ("zona sul", "São Paulo", "no Morumbi, com muito verde e privacidade", False,
                       "no Jardim Guedala"),
}  # fmt: skip

OFFICE_TYPES = ("conjunto comercial", "andar corporativo", "laje corporativa")

# tipo: (bairros, faixa de área, cap rate % a.a. (retorno do aluguel sobre o preço), aluguel R$/m²/mês,
#        quantidade, fração à venda). O preço de venda sai do aluguel pelo cap rate, então tudo fica coerente.
TYPES = {
    "conjunto comercial": (["Itaim Bibi", "Vila Olímpia", "Pinheiros", "Brooklin", "Cidade Monções",
                            "Chácara Santo Antônio", "Bela Vista", "Cerqueira César", "Paraíso", "Vila Madalena",
                            "Jardins", "Moema", "Vila Mariana", "Barra Funda", "Alphaville"], (80, 800),
                           (6.5, 8.0), (85, 180), 24, 0.35),
    "andar corporativo": (["Itaim Bibi", "Vila Olímpia", "Pinheiros", "Jardim Europa", "Brooklin",
                           "Chácara Santo Antônio", "Cidade Monções", "Bela Vista", "Vila Leopoldina", "Alphaville"],
                          (450, 3000), (6.3, 7.8), (120, 240), 14, 0.3),
    "laje corporativa": (["Vila Olímpia", "Itaim Bibi", "Pinheiros", "Chácara Santo Antônio", "Brooklin",
                          "Barra Funda", "Vila Leopoldina"], (900, 5000), (6.5, 8.0), (95, 190), 8, 0.35),
    "prédio comercial": (["Vila Olímpia", "Itaim Bibi", "Jardins", "Liberdade", "Paraíso", "Brooklin",
                          "Vila Mariana", "Pinheiros"], (600, 15000), (7.0, 8.5), (70, 200), 8, 0.5),
    "galpão": (["Guarulhos", "Cajamar", "Jundiaí", "Extrema", "Araçariguama", "Embu das Artes", "Itapevi",
                "Vila Leopoldina", "Jaguaré", "Alphaville"], (1500, 32000), (7.8, 9.5), (22, 40), 14, 0.4),
}  # fmt: skip

# endereços mais disputados valem mais (multiplicador sobre a faixa do tipo)
PREMIUM = {"Itaim Bibi": 1.3, "Jardim Europa": 1.3, "Vila Olímpia": 1.2, "Pinheiros": 1.1, "Cidade Monções": 1.05,
           "Chácara Santo Antônio": 0.9, "Barra Funda": 0.8, "Liberdade": 0.75, "Vila Leopoldina": 0.85,
           "Alphaville": 0.65, "Vila Mariana": 0.85, "Moema": 0.9}  # fmt: skip
# galpões: última milha dentro da capital vale mais; interior vale menos
LOGISTICS_PREMIUM = {"Vila Leopoldina": 1.35, "Jaguaré": 1.25, "Guarulhos": 1.1, "Alphaville": 1.05,
                     "Extrema": 0.8, "Araçariguama": 0.75, "Jundiaí": 0.85}  # fmt: skip

ACTIVITIES = {
    "conjunto comercial": [["escritório"], ["escritório", "clínica"], ["escritório", "coworking"],
                           ["escritório", "consultório", "clínica"]],
    "andar corporativo": [["escritório"], ["escritório", "coworking"]],
    "laje corporativa": [["escritório"], ["escritório", "coworking"]],
    "prédio comercial": [["escritório", "educação"], ["escritório", "clínica", "educação"], ["escritório", "coworking"]],
    "galpão": [["logística", "armazenagem"], ["logística", "armazenagem", "e-commerce"],
               ["indústria leve", "armazenagem"]],
}  # fmt: skip
CLINIC_PLACES = {"Moema", "Vila Mariana", "Paraíso", "Cerqueira César", "Jardins", "Bela Vista"}

# nomes fictícios (árvores brasileiras), para não usar edifícios reais
BUILDINGS = ["Edifício Ipê", "Jatobá Corporate", "Aroeira Office", "Edifício Jequitibá", "Paineira Business",
             "Cedro Corporate", "Edifício Sibipiruna", "Tarumã Office", "Angico Trade Center", "Edifício Pau-Brasil",
             "Cambuí Corporate", "Edifício Guarantã", "Jacarandá Office", "Figueira Business Center", "Edifício Canela",
             "Peroba Corporate", "Imbuia Office", "Edifício Araucária", "Buriti Corporate", "Edifício Manacá",
             "Edifício Mogno", "Cumaru Office", "Edifício Copaíba", "Andiroba Corporate", "Edifício Carnaúba",
             "Babaçu Business", "Edifício Pequi", "Juçara Office", "Edifício Oiti", "Embaúba Corporate"]  # fmt: skip
_buildings_by_place: dict[str, list[str]] = {}


def building_in(place: str) -> str:
    """Cada bairro tem os seus edifícios (2 nos polos AAA, 1 nos demais): imóveis do bairro dividem o prédio."""
    names = _buildings_by_place.setdefault(place, [])
    if not names or (place in AAA_PLACES and len(names) < 2 and random.random() < 0.5):
        names.append(BUILDINGS[sum(len(v) for v in _buildings_by_place.values()) % len(BUILDINGS)])
    return random.choice(names)


# moda da distribuição de área (fração da faixa): a maioria dos imóveis fica perto do mínimo
MODE = {"conjunto comercial": 0.1, "galpão": 0.04}
AAA_PLACES = {"Itaim Bibi", "Jardim Europa", "Vila Olímpia", "Chácara Santo Antônio", "Cidade Monções", "Pinheiros"}

OFFICE_SPECS = ["ar-condicionado VRF", "piso elevado", "forro modular", "controle de acesso", "CFTV",
                "elevadores com antecipação de chamada", "automação predial", "gerador 100%", "segurança 24h",
                "estacionamento com manobrista", "bicicletário e vestiários", "auditório", "copa"]  # fmt: skip
PREMIUM_SPECS = ["heliponto", "restaurante no edifício", "lajes sem pilares", "lobby com pé-direito duplo"]
SHELL_SPECS = ["controle de acesso", "CFTV", "elevadores com antecipação de chamada", "automação predial",
               "gerador 100%", "segurança 24h", "estacionamento com manobrista", "bicicletário e vestiários",
               "planta livre", "shafts para ar-condicionado"]  # fmt: skip
BUILDING_SPECS = ["elevadores", "fachada ativa", "gerador", "estacionamento próprio", "retrofit recente", "terraço",
                  "auditório", "ar-condicionado central", "entrada independente"]  # fmt: skip
WAREHOUSE_SPECS = ["docas com niveladoras", "sprinklers", "pátio de manobras para carretas", "escritório "
                   "administrativo", "vestiários", "portaria blindada e segurança 24h", "cabine primária",
                   "iluminação LED", "cobertura com isolamento térmico", "rua interna para veículos"]  # fmt: skip

ACCESS = {"Guarulhos": "Via Dutra", "Cajamar": "Rodovia Anhanguera", "Jundiaí": "Rodovia dos Bandeirantes",
          "Extrema": "Rodovia Fernão Dias", "Araçariguama": "Castello Branco", "Embu das Artes": "Régis Bittencourt",
          "Itapevi": "Castello Branco", "Vila Leopoldina": "Marginal Pinheiros", "Jaguaré": "Rodoanel",
          "Alphaville": "Castello Branco"}  # fmt: skip

# inquilinos dos imóveis à venda já locados, com a atividade que exercem (entra nas atividades permitidas)
TENANTS = {
    "conjunto comercial": {"empresa de tecnologia": "escritório", "escritório de advocacia": "escritório",
                           "seguradora": "escritório", "rede de clínicas": "clínica"},
    "andar corporativo": {"banco digital": "escritório", "multinacional de bens de consumo": "escritório",
                          "consultoria": "escritório", "gestora de investimentos": "escritório"},
    "laje corporativa": {"banco digital": "escritório", "empresa de tecnologia": "escritório",
                         "multinacional farmacêutica": "escritório"},
    "prédio comercial": {"faculdade": "educação", "rede de clínicas": "clínica", "empresa de call center": "escritório"},
    "galpão": {"operador logístico": "logística", "e-commerce de moda": "e-commerce",
               "distribuidora de alimentos": "armazenagem", "indústria farmacêutica": "indústria leve"},
}  # fmt: skip

DETAILS = {
    "conjunto comercial": "Conjunto com planta flexível, fácil de adaptar para escritório aberto, salas de reunião "
    "ou clínica.",
    "andar corporativo": "Andar corporativo inteiro, entregue com acabamento e pronto para receber a operação.",
    "laje corporativa": "Laje entregue no contrapiso (core & shell), para a empresa montar o próprio projeto de "
    "interiores.",
    "prédio comercial": "Prédio inteiro para uso de uma única empresa (monousuário), com identidade própria na fachada.",
    "galpão": "Galpão em condomínio logístico, com estrutura para armazenagem e distribuição e fácil acesso de "
    "carretas.",
}

# residenciais de alto padrão à venda: (tipo, bairro, faixa de área, quartos, suítes, vagas, R$/m²)
RESIDENTIAL = [
    ("cobertura", "Jardim Guedala", (900, 1250), 4, 4, 10, 11000),
    ("apartamento", "Vila Nova Conceição", (480, 600), 4, 4, 6, 36000),
    ("apartamento", "Itaim Bibi", (350, 470), 4, 4, 5, 28000),
    ("apartamento", "Jardim Europa", (280, 380), 3, 3, 4, 30000),
    ("apartamento", "Moema", (170, 240), 3, 3, 3, 19000),
    ("casa", "Alto de Pinheiros", (600, 900), 5, 4, 6, 16000),
    ("casa", "Cidade Jardim", (900, 1400), 5, 5, 8, 17000),
    ("studio", "Vila Olímpia", (28, 40), 1, 1, 1, 21000),
]
RESIDENTIAL_AMENITIES = ["piscina", "academia", "varanda gourmet", "segurança 24h", "vista para o parque", "adega",
                         "home theater", "sauna", "quadra de tênis", "jardim", "espaço gourmet", "lareira"]  # fmt: skip


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def decimal(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}{suffix if n != 1 else ''}"


def round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def area_step(area: int) -> int:
    return 5 if area < 200 else 10 if area < 1000 else 50 if area < 10000 else 100


def title_for(tipo: str, place: str, area: int, features: dict, leased: dict | None) -> str:
    ref = PLACES[place][4]
    building = features.get("edificio") or features.get("condominio")
    if leased:
        noun = {"galpão": "Galpão locado", "conjunto comercial": "Conjunto locado", "laje corporativa": "Laje locada",
                "andar corporativo": "Andar corporativo locado", "prédio comercial": "Prédio locado"}[tipo]  # fmt: skip
        return f"{noun} para {leased['inquilino']} {ref}"
    options = {
        "conjunto comercial": [f"Conjunto comercial de {fmt_int(area)} m² {ref}",
                               f"Conjunto no {building}, {ref.split(' ', 1)[1]}"],
        "andar corporativo": [f"Andar corporativo de {fmt_int(area)} m² {ref}",
                              f"Andar inteiro no {building}, {ref.split(' ', 1)[1]}"],
        "laje corporativa": [f"Laje corporativa de {fmt_int(area)} m² {ref}",
                             f"Laje core & shell de {fmt_int(area)} m² {ref}"],
        "galpão": [f"Galpão logístico de {fmt_int(area)} m² {ref}",
                   f"Galpão com {plural(features.get('docas', 2), 'doca')} {ref}"],
        "prédio comercial": [f"Prédio comercial de {features.get('andares', 4)} andares {ref}",
                             f"Edifício monousuário de {fmt_int(area)} m² {ref}"],
    }[tipo]  # fmt: skip
    return random.choice(options)


def build_property(idx: int, tipo: str, place: str, purpose: str, leased_sale: bool) -> dict:
    zone, city, profile, metro, _ = PLACES[place]
    _, (a_min, a_max), (cap_min, cap_max), (r_min, r_max), _, _ = TYPES[tipo]
    area = int(random.triangular(a_min, a_max, a_min + (a_max - a_min) * MODE.get(tipo, 0.2)))
    area = round_to(area, area_step(area))
    mult = LOGISTICS_PREMIUM.get(place, 1.0) if tipo == "galpão" else PREMIUM.get(place, 1.0)
    monthly_rent = area * random.uniform(r_min, r_max) * mult
    sale_price = monthly_rent * 12 / (random.uniform(cap_min, cap_max) / 100)

    atividades = random.choice(ACTIVITIES[tipo])
    if tipo == "conjunto comercial" and place in CLINIC_PLACES and "clínica" not in atividades:
        atividades = [*atividades, "clínica"]
    features: dict = {"atividades": atividades}
    if tipo in OFFICE_TYPES:
        features["edificio"] = building_in(place)
        features["classe"] = "AAA" if place in AAA_PLACES and random.random() < 0.7 else random.choice(["AA", "A"])
        if features["classe"] == "AAA" or random.random() < 0.2:
            features["certificacao"] = random.choice(["LEED Gold", "LEED Gold", "LEED Platinum"])
        features["andar"] = random.randint(2, 28 if features["classe"] == "AAA" else 16)
        features["entrega"] = "core & shell" if tipo == "laje corporativa" else "pronto para uso"
        pool = SHELL_SPECS if tipo == "laje corporativa" else OFFICE_SPECS
        highlights = random.sample(pool, 5)
        if features["classe"] == "AAA":
            highlights += random.sample(PREMIUM_SPECS, 2)
        bathrooms = {"conjunto comercial": random.randint(2, 6), "andar corporativo": random.randint(4, 14),
                     "laje corporativa": random.randint(6, 16)}[tipo]  # fmt: skip
        parking = max(2, round(area / random.uniform(35, 60)))
        condo = round_to(area * random.uniform(24, 40) * (1.1 if features["classe"] == "AAA" else 1), 10)
    elif tipo == "galpão":
        features["condominio"] = f"Parque Logístico {place} {random.choice(['I', 'II', 'III'])}"
        features["pe_direito_m"] = round(random.uniform(10, 14), 1)
        features["docas"] = max(4, round(area / random.uniform(600, 1100)))
        features["piso_carga_ton_m2"] = random.choice([5, 6, 6, 8])
        features["acesso"] = ACCESS[place]
        highlights = random.sample(WAREHOUSE_SPECS, 5)
        bathrooms = random.randint(4, 16)
        parking = random.randint(20, 120)
        condo = round_to(area * random.uniform(3, 6), 10)
    else:  # prédio comercial
        features["andares"] = max(3, min(24, round(area / random.uniform(500, 900))))
        features["elevadores"] = max(1, features["andares"] // 4)
        highlights = random.sample(BUILDING_SPECS, 5)
        bathrooms = features["andares"] * 2
        parking = round(area / random.uniform(45, 80))
        condo = None
    features["destaques"] = highlights

    leased = None
    if purpose == "venda" and leased_sale:
        rent = round_to(monthly_rent * random.uniform(0.92, 1.05), 100)
        tenant = random.choice(list(TENANTS[tipo]))
        leased = {"inquilino": tenant, "contrato_ate": random.randint(2027, 2033), "aluguel_atual": rent}
        if TENANTS[tipo][tenant] not in features["atividades"]:
            features["atividades"] = [*features["atividades"], TENANTS[tipo][tenant]]
        features["locado"] = leased
        sale_price = rent * 12 / (random.uniform(cap_min, cap_max) / 100)  # vendido pelo cap rate
    rent_yield = (leased["aluguel_atual"] if leased else monthly_rent) * 12 / sale_price * 100

    furnished = tipo == "conjunto comercial" and random.random() < 0.25
    if furnished:
        highlights.append("mobiliado e pronto para uso")
        features["entrega"] = "mobiliado"

    specs = [f"São {fmt_int(area)} m²"]
    if parking:
        specs.append(plural(parking, "vaga"))
    if "docas" in features:
        specs.append(
            f"{plural(features['docas'], 'doca')}, pé-direito de {decimal(features['pe_direito_m'])} m e "
            f"piso para {features['piso_carga_ton_m2']} t/m²"
        )
    elif "andar" in features:
        specs.append(f"{features['andar']}º andar")
    elif "andares" in features:
        specs.append(f"{features['andares']} andares e {plural(features['elevadores'], 'elevador', 'es')}")
    if "edificio" in features:
        cert = f", com certificação {features['certificacao']}" if features.get("certificacao") else ""
        intro = f"O {features['edificio']} é um edifício corporativo classe {features['classe']}{cert}, {profile}."
    elif "condominio" in features:
        intro = f"O {features['condominio']} fica em {place}, {profile}, com acesso pela {features['acesso']}."
    else:
        intro = random.choice([f"Localização estratégica em {place}: {profile}.",
                               f"Excelente oportunidade em {place}: {profile}."])  # fmt: skip
    parts = [intro, DETAILS[tipo], ", ".join(specs) + ".", f"Permite: {', '.join(features['atividades'])}."]
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


def build_residential(idx: int, tipo: str, place: str, area_range: tuple[int, int], bedrooms: int, suites: int,
                      parking: int, price_m2: int) -> dict:  # fmt: skip
    zone, city, profile, metro, ref = PLACES[place]
    ref = f"no {place}" if place == "Itaim Bibi" else ref
    area = round_to(random.uniform(*area_range), 5 if tipo == "studio" else 10)
    price = round_to(area * price_m2 * random.uniform(0.9, 1.1), 50000 if area > 100 else 10000)
    amenities = random.sample(RESIDENTIAL_AMENITIES, 4)
    title = {
        "cobertura": f"Cobertura de {fmt_int(area)} m² {ref}",
        "apartamento": f"Apartamento de {plural(suites, 'suíte')} {ref}",
        "casa": f"Casa de {fmt_int(area)} m² {ref}",
        "studio": f"Studio para investir {ref}",
    }[tipo]
    rooms = f"{plural(bedrooms, 'quarto')}" + (f", sendo {plural(suites, 'suíte')}" if suites else "")
    description = (
        f"{title}, {profile}. São {fmt_int(area)} m², {rooms} e {plural(parking, 'vaga')}. "
        + ("Ótimo para renda com locação de curta ou longa temporada. " if tipo == "studio" else "")
        + f"Destaques: {', '.join(amenities)}."
    )
    return {
        "id": f"IMV-{idx:03d}",
        "title": title,
        "segment": "residencial",
        "property_type": tipo,
        "purpose": "venda",
        "neighborhood": place,
        "zone": zone,
        "city": city,
        "price": price,
        "condo_fee": None if tipo == "casa" else round_to(area * random.uniform(18, 30), 100),
        "iptu": round_to(price * 0.006 / 12, 10),
        "bedrooms": bedrooms,
        "suites": suites,
        "bathrooms": suites + 1,
        "parking": parking,
        "area_m2": area,
        "description": description,
        "amenities": amenities,
        "features": {},
        "furnished": tipo == "studio",
        "pet_friendly": True,
        "accepts_financing": True,
        "estimated_yield": round(random.uniform(5.5, 6.5) if tipo == "studio" else random.uniform(3.5, 4.5), 2),
        "near_metro": tipo == "studio" or (metro and random.random() < 0.5),
        "available": True,
    }


def main() -> None:
    properties = []
    idx = 1
    for tipo, (places, _, _, _, count, sale_share) in TYPES.items():
        for i in range(count):
            place = places[i % len(places)]
            purpose = "venda" if random.random() < sale_share else "aluguel"
            leased_sale = purpose == "venda" and random.random() < 0.6
            properties.append(build_property(idx, tipo, place, purpose, leased_sale))
            idx += 1
    for spec in RESIDENTIAL:
        properties.append(build_residential(idx, *spec))
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
