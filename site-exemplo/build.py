"""Gera o site estático da "Imobiliária Exemplo" (fictícia) com o widget da Laris embutido.

Visual de imobiliária de real estate corporativo de São Paulo: azul-marinho sóbrio, busca por pretensão (alugar,
comprar, investir), cards com código do imóvel, página do imóvel com "pacote de locação" (aluguel + condomínio +
IPTU), especificações técnicas e formulário "Fale com a imobiliária", que abre a Laris com a mensagem pronta.

A base de imóveis é a mesma da ImobiQ (data/properties.json), então a Laris conhece cada imóvel do site.

Uso:
    python site-exemplo/build.py                                   # widget local (http://localhost:3001)
    python site-exemplo/build.py --widget https://imobiq.arrtsoftware.com.br/widget.js --zip

Saída em site-exemplo/dist/ (é só subir essa pasta para qualquer hospedagem estática). Com --zip, gera também
site-exemplo/imobiliaria-exemplo.zip para o Gerenciador de Arquivos da Hostinger (extrair na pasta do subdomínio).
"""

import argparse
import json
import shutil
import zipfile
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "properties.json"
DIST = ROOT / "dist"
BRAND = "Imobiliária Exemplo"

TYPES = {  # tipo: (singular, plural, matiz da ilustração)
    "conjunto comercial": ("Conjunto comercial", "Conjuntos comerciais", 222),
    "andar corporativo": ("Andar corporativo", "Andares corporativos", 214),
    "laje corporativa": ("Laje corporativa", "Lajes corporativas", 230),
    "prédio comercial": ("Prédio comercial", "Prédios comerciais", 205),
    "galpão": ("Galpão", "Galpões", 200),
    "apartamento": ("Apartamento", "Apartamentos", 238),
    "cobertura": ("Cobertura", "Coberturas", 245),
    "casa": ("Casa", "Casas", 190),
    "studio": ("Studio", "Studios", 250),
}
COMMERCIAL = ["conjunto comercial", "andar corporativo", "laje corporativa", "prédio comercial", "galpão"]
UF = {"Extrema": "MG"}
TELEGRAM = "imobiq_laris_bot"  # bot da Laris no Telegram (--telegram troca)
TG_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18"><path fill="currentColor" d="M21.'
    "4 3.6 2.9 10.7c-1.3.5-1.3 1.2-.2 1.5l4.7 1.5 1.8 5.6c.2.6.1.9.8.9.5 0 .7-.2 1-.5l2.3-2.2 4.7 3.5c.9."
    '5 1.5.2 1.7-.8l3.1-14.6c.3-1.3-.5-1.9-1.4-1.5ZM8.9 13.3l9.3-5.9c.5-.3.9-.1.5.2l-7.9 7.2-.3 3.3z"/></'
    "svg>"
)
FEATURED = ["IMV-025", "IMV-026", "IMV-009", "IMV-055", "IMV-006", "IMV-042", "IMV-049", "IMV-076"]


def brl(value: int | None) -> str:
    return f"R$ {value:,.0f}".replace(",", ".") if value else "—"


def num(value: float) -> str:
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


def plural(n: int, word: str, suffix: str = "s") -> str:
    return f"{n} {word}{suffix if n != 1 else ''}"


def page_name(p: dict) -> str:
    return f"imovel-{p['id'].lower()}.html"


def singular(p: dict) -> str:
    return TYPES.get(p["property_type"], (p["property_type"].capitalize(),))[0]


def location(p: dict, sep: str = " - ") -> str:
    """Bairro - Cidade - UF (sem repetir a cidade quando o bairro é a própria cidade)."""
    parts = [p["neighborhood"], p["city"], UF.get(p["city"], "SP")]
    if p["neighborhood"] == p["city"]:
        parts.pop(0)
    return sep.join(parts)


def exclusive(p: dict) -> bool:
    """Alguns imóveis com exclusividade (como nas carteiras reais), escolhidos de forma determinística."""
    return not p["features"].get("locado") and int(p["id"][-3:]) % 6 == 1


def headline(p: dict) -> str:
    """Título no formato das imobiliárias: tipo, finalidade, área, preço e localização."""
    area = f"{num(p['area_m2'])} m²"
    where = f"{p['neighborhood']}, {p['city']}/{UF.get(p['city'], 'SP')}"
    if p["neighborhood"] == p["city"]:
        where = f"{p['city']}/{UF.get(p['city'], 'SP')}"
    if p["purpose"] == "aluguel":
        return f"{singular(p)} para alugar, {area} por {brl(p['price'])}/mês · {where}"
    leased = " locado" if p["features"].get("locado") else ""
    return f"{singular(p)}{leased} à venda, {area} por {brl(p['price'])} · {where}"


# ---------------------------------------------------------------- ícones e ilustrações (sem fotos)

SM = {  # ícones pequenos (traço), 16x16
    "area": '<path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/>',
    "bath": '<path d="M2 8h12v2a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4z"/><path d="M4 8V4a2 2 0 0 1 4 0"/>',
    "car": '<path d="M3 11V8l1.5-4h7L13 8v3z"/><path d="M3 11v2M13 11v2M5 9h.01M11 9h.01"/>',
    "bed": '<path d="M2 12V5M2 9h12v3M14 12V9a2 2 0 0 0-2-2H7v2"/>',
    "dock": '<path d="M2 14V6l6-3 6 3v8"/><path d="M5 14V9h6v5"/>',
    "floor": '<path d="M4 14V2h8v12M2 14h12M6 5h1M9 5h1M6 8h1M9 8h1"/>',
}


def sm(name: str) -> str:
    return (
        f'<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4" '
        f'stroke-linecap="round" stroke-linejoin="round">{SM[name]}</svg>'
    )


ART = {
    "conjunto comercial": '<rect x="30" y="18" width="60" height="52" rx="2"/><path d="M38 28h10M56 28h10M74 28h8'
    'M38 40h10M56 40h10M74 40h8M38 52h10M56 52h10M74 52h8"/><path d="M22 70h76"/>',
    "andar corporativo": '<path d="M42 70V12h36v58"/><path d="M48 20h24M48 28h24M48 36h24M48 44h24M48 52h24"/>'
    '<rect x="46" y="31" width="28" height="10" rx="1" fill="currentColor" fill-opacity=".25"/><path d="M22 70h76"/>',
    "laje corporativa": '<path d="M44 70V14h32v56"/><path d="M50 22h20M50 30h20M50 38h20M50 46h20M50 54h20"/>'
    '<path d="M32 70V40h12M76 34h12v36"/><path d="M22 70h76"/>',
    "prédio comercial": '<rect x="38" y="14" width="44" height="56" rx="2"/><path d="M46 24h8M66 24h8M46 36h8M66 36h8'
    'M46 48h8M66 48h8"/><path d="M54 70V60h12v10"/><path d="M26 70h68"/>',
    "galpão": '<path d="M22 70V38l38-18 38 18v32"/><path d="M36 70V50h14v20M56 70V50h14v20"/>'
    '<path d="M76 56h12"/><path d="M16 70h88"/>',
    "apartamento": '<rect x="40" y="16" width="40" height="54" rx="2"/><path d="M47 26h8M65 26h8M47 38h8M65 38h8'
    'M47 50h8M65 50h8"/><path d="M56 70v-9h8v9"/><path d="M26 70h68"/>',
    "cobertura": '<path d="M40 70V26h40v44"/><path d="M36 26h48M44 26V18h32v8"/><path d="M47 36h8M65 36h8M47 48h8'
    'M65 48h8"/><path d="M26 70h68"/>',
    "casa": '<path d="M30 70V42l30-22 30 22v28"/><path d="M52 70V54h16v16"/><path d="M38 48h8M74 48h8"/>'
    '<path d="M20 70h80"/>',
    "studio": '<rect x="44" y="22" width="32" height="48" rx="2"/><path d="M50 32h20M50 42h20M50 52h20"/>'
    '<path d="M30 70h60"/>',
}


def illustration(p: dict, big: bool = False) -> str:
    hue = TYPES.get(p["property_type"], ("", "", 220))[2]
    badges = []
    if exclusive(p):
        badges.append('<span class="badge gold">Exclusivo</span>')
    if p["features"].get("locado"):
        badges.append('<span class="badge">Locado · renda</span>')
    if p["features"].get("classe") == "AAA":
        badges.append('<span class="badge ghost">AAA</span>')
    note = '<span class="art-note">Imagem ilustrativa</span>' if big else ""
    return (
        f'<div class="art{" art-big" if big else ""}" style="--h:{hue}">'
        f'<svg viewBox="0 0 120 90" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2.4" '
        f'stroke-linecap="round" stroke-linejoin="round">{ART.get(p["property_type"], ART["conjunto comercial"])}</g>'
        f'</svg><span class="badges">{"".join(badges)}</span>{note}</div>'
    )


def facts(p: dict) -> list[tuple[str, str]]:
    """Os números que aparecem no card e no topo da página do imóvel (ícone, texto)."""
    f = p["features"]
    items = [("area", f"{num(p['area_m2'])} m²")]
    if p["segment"] == "residencial":
        items += [("bed", plural(p["bedrooms"], "quarto")), ("bath", plural(p["suites"], "suíte"))]
    elif f.get("docas"):
        items += [("dock", plural(f["docas"], "doca")), ("floor", f"pé-direito {num(f['pe_direito_m'])} m")]
    else:
        items.append(("bath", plural(p["bathrooms"], "banheiro")))
    if p["parking"]:
        items.append(("car", plural(p["parking"], "vaga")))
    return items


def facts_html(p: dict) -> str:
    return "".join(f"<li>{sm(icon)}{escape(text)}</li>" for icon, text in facts(p))


def search_text(p: dict) -> str:
    f = p["features"]
    words = [p["title"], p["neighborhood"], p["city"], p["zone"], singular(p), f.get("edificio", ""),
             f.get("condominio", ""), f.get("acesso", ""), p["id"]]  # fmt: skip
    return " ".join(w for w in words if w)


# ---------------------------------------------------------------- blocos comuns

LAYOUT_HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {brand}</title>
<meta name="description" content="Site fictício de imobiliária corporativa para demonstrar o widget da Laris (ImobiQ).">
<meta name="robots" content="noindex">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" href="assets/logo.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;500;700;900&family=Open+Sans:wght@400;600;700&display=swap">
<link rel="stylesheet" href="assets/style.css">
</head>
"""


def logo(small: bool = False) -> str:
    size = 30 if small else 38
    return (
        f'<img src="assets/logo.svg" alt="" width="{size}" height="{size}">'
        f'<span class="logo-text"><b>Imobiliária Exemplo</b><small>Negócios imobiliários</small></span>'
    )


def layout(title: str, body: str, widget: str, footer: str, property_id: str | None = None, active: str = "") -> str:
    data_property = f' data-property="{property_id}"' if property_id else ""

    def nav(href: str, label: str, key: str) -> str:
        current = ' aria-current="page"' if key == active else ""
        return f'<a href="{href}"{current}>{label}</a>'

    return (
        LAYOUT_HEAD.format(title=escape(title), brand=BRAND)
        + f"""<body>
<p class="demo-bar">Site fictício para demonstrar a integração com a <b>ImobiQ</b>. Imóveis, edifícios e endereços
são simulados.</p>
<div class="util">
  <div class="wrap util-in">
    <span>Consultoria imobiliária · Real estate corporativo</span>
    <button class="util-link" type="button" onclick="window.ImobiQ && ImobiQ.open()">
      Atendimento 24h com a Laris</button>
  </div>
</div>
<header class="top">
  <div class="wrap top-in">
    <a class="logo" href="index.html" aria-label="{BRAND}, página inicial">{logo()}</a>
    <nav aria-label="Principal">
      {nav("imoveis.html?finalidade=aluguel", "Alugar", "aluguel")}
      {nav("imoveis.html?finalidade=venda", "Comprar", "venda")}
      {nav("imoveis.html?finalidade=investir", "Investir", "investir")}
      <button class="nav-link" type="button" data-laris="Quero encomendar um imóvel. Minha empresa procura ">
        Encomende seu imóvel</button>
      {nav("index.html#sobre", "Quem somos", "sobre")}
    </nav>
    <button class="btn btn-light" type="button" onclick="window.ImobiQ && ImobiQ.open()">Fale com especialista</button>
  </div>
</header>
<main>
{body}
</main>
{footer}
<script src="assets/site.js" defer></script>
<script src="{widget}" data-brand="{BRAND}"{data_property} defer></script>
</body>
</html>
"""
    )


def telegram_link(css: str) -> str:
    if not TELEGRAM:
        return ""
    return f'<a class="{css}" href="https://t.me/{TELEGRAM}" target="_blank" rel="noopener">{TG_ICON} Telegram</a>'


def footer_html(props: dict[str, dict]) -> str:
    combos = []
    for t in COMMERCIAL + ["apartamento", "cobertura", "casa", "studio"]:
        for purpose, label in (("aluguel", "para alugar"), ("venda", "à venda")):
            if any(p["property_type"] == t and p["purpose"] == purpose for p in props.values()):
                href = f"imoveis.html?finalidade={purpose}&amp;tipo={escape(t)}"
                combos.append(f'<li><a href="{href}">{TYPES[t][1]} {label}</a></li>')
    hoods = Counter(p["neighborhood"] for p in props.values() if p["segment"] == "comercial")
    hood_links = "".join(
        f'<li><a href="imoveis.html?q={escape(h)}">{escape(h)}</a></li>' for h, _ in hoods.most_common(12)
    )
    buildings = Counter(p["features"]["edificio"] for p in props.values() if p["features"].get("edificio"))
    building_links = "".join(
        f'<li><a href="imoveis.html?q={escape(b)}">{escape(b)}</a></li>' for b, _ in buildings.most_common(10)
    )
    return f"""<footer class="foot" id="contato">
  <div class="wrap foot-grid">
    <div class="foot-brand">
      <p class="logo">{logo(small=True)}</p>
      <p class="foot-units"><b>Unidade Faria Lima</b><br>Av. Exemplo, 1000 · 12º andar<br>Itaim Bibi · São Paulo/SP</p>
      <p class="foot-units"><b>Unidade Berrini</b><br>Rua Fictícia, 200 · 8º andar<br>Brooklin · São Paulo/SP</p>
      <p class="foot-units"><b>Horário</b><br>Corretores: seg. a sex., 9h às 18h<br>Laris: 24 horas, todos os dias</p>
      <div class="foot-cta">
        <button class="btn btn-light" type="button" onclick="window.ImobiQ && ImobiQ.open()">
          Fale agora com a Laris</button>
        {telegram_link("btn btn-ghost")}
      </div>
    </div>
    <div><p class="foot-title">Descubra outras possibilidades</p><ul class="foot-links">{"".join(combos)}</ul></div>
    <div><p class="foot-title">Bairros mais procurados</p><ul class="foot-links">{hood_links}</ul></div>
    <div><p class="foot-title">Edifícios</p><ul class="foot-links">{building_links}</ul></div>
  </div>
  <p class="wrap fine">CRECI 00000-J (fictício) · Imobiliária fictícia criada para o Hackathon FIAP Pós Tech
  IA para Devs · atendimento virtual por ImobiQ</p>
</footer>"""


def card(p: dict) -> str:
    leased = p["features"].get("locado")
    label = "Aluguel" if p["purpose"] == "aluguel" else "Venda"
    price = f"{brl(p['price'])}<small>/mês</small>" if p["purpose"] == "aluguel" else brl(p["price"])
    note = (
        f'<p class="leased">Locado para {escape(leased["inquilino"])} · {num(p["estimated_yield"])}% a.a.</p>'
        if leased
        else ""
    )
    return (
        f'<article class="card" data-purpose="{p["purpose"]}" data-type="{escape(p["property_type"])}" '
        f'data-area="{p["area_m2"]}" data-price="{p["price"]}" data-leased="{1 if leased else 0}" '
        f'data-search="{escape(search_text(p))}">'
        f'<a href="{page_name(p)}">{illustration(p)}'
        f'<div class="card-body"><p class="code">{p["id"]}</p>'
        f'<h3 class="ctype">{escape(singular(p))}</h3>'
        f'<p class="where">{escape(location(p))}</p>'
        f'<ul class="facts">{facts_html(p)}</ul>'
        f'<div class="card-price"><span>{label}</span><p class="price">{price}</p></div>{note}'
        f"</div></a></article>"
    )


def type_options(types: list[str]) -> str:
    return "".join(f'<option value="{escape(t)}">{TYPES[t][0]}</option>' for t in types)


def place_options(props: dict[str, dict]) -> str:
    names = sorted({p["neighborhood"] for p in props.values()} | {p["city"] for p in props.values()})
    names += sorted({p["features"]["edificio"] for p in props.values() if p["features"].get("edificio")})
    return "".join(f'<option value="{escape(n)}"></option>' for n in names)


def present_types(props: dict[str, dict]) -> list[str]:
    return [t for t in TYPES if any(p["property_type"] == t for p in props.values())]


# ---------------------------------------------------------------- páginas


def home(props: dict[str, dict], widget: str, footer: str) -> str:
    featured = "".join(card(props[code]) for code in FEATURED if code in props)
    tiles = []
    for t in COMMERCIAL:
        for purpose, label in (("aluguel", "para alugar"), ("venda", "à venda")):
            n = sum(p["property_type"] == t and p["purpose"] == purpose for p in props.values())
            if n:
                href = f"imoveis.html?finalidade={purpose}&amp;tipo={escape(t)}"
                tiles.append(f'<a class="tile" href="{href}"><b>{TYPES[t][1]}</b><span>{label} · {n}</span></a>')
    leased = sum(bool(p["features"].get("locado")) for p in props.values())
    body = f"""
<section class="hero">
  <div class="skyline" aria-hidden="true"></div>
  <div class="wrap hero-in">
    <p class="eyebrow">Negócios imobiliários</p>
    <h1>Consultoria imobiliária<br><span>real estate corporativo</span></h1>
    <p class="lead">Andares corporativos, conjuntos, prédios e galpões logísticos em São Paulo e região, para
    alugar, comprar ou investir.</p>
    <form class="search" action="imoveis.html" method="get" aria-label="Buscar imóveis">
      <fieldset class="tabs">
        <legend class="sr-only">Pretensão</legend>
        <label><input type="radio" name="finalidade" value="aluguel" checked><span>Alugar</span></label>
        <label><input type="radio" name="finalidade" value="venda"><span>Comprar</span></label>
        <label><input type="radio" name="finalidade" value="investir"><span>Investir</span></label>
      </fieldset>
      <div class="search-row">
        <label class="field">Tipo de imóvel<select name="tipo"><option value="">Todos</option>
          {type_options(present_types(props))}</select></label>
        <label class="field grow">Onde<input name="q" list="places" autocomplete="off"
          placeholder="Digite edifício, região, bairro ou cidade"></label>
        <button class="btn btn-primary" type="submit">Encontrar imóvel</button>
      </div>
      <datalist id="places">{place_options(props)}</datalist>
    </form>
    <form class="code-search" id="code-search" aria-label="Busca por código">
      <label>Busca por código <input name="code" placeholder="IMV-025" autocomplete="off" maxlength="7"></label>
      <button type="submit">Ir</button>
    </form>
  </div>
</section>

<section class="wrap block">
  <div class="block-head"><h2>Encontre por tipo</h2><a href="imoveis.html">Ver todos os imóveis →</a></div>
  <div class="tiles">{"".join(tiles)}</div>
</section>

<section class="wrap block">
  <div class="block-head"><h2>Imóveis em destaque</h2><a href="imoveis.html">Ver todos →</a></div>
  <div class="grid">{featured}</div>
</section>

<section class="services">
  <div class="wrap services-grid">
    <article class="service">
      <h3>Imóvel sob encomenda</h3>
      <p>Descreva o imóvel que a sua empresa procura. A Laris faz a pesquisa na hora e o especialista continua
      a busca personalizada.</p>
      <button class="btn btn-outline" type="button"
        data-laris="Quero encomendar um imóvel. Minha empresa procura ">Encomende seu imóvel</button>
    </article>
    <article class="service">
      <h3>Investir com renda</h3>
      <p>{leased} imóveis já locados, com inquilino e contrato em vigor: renda desde o primeiro mês, com análise
      de cap rate e garantias.</p>
      <a class="btn btn-outline" href="imoveis.html?finalidade=investir">Ver imóveis locados</a>
    </article>
    <article class="service service-laris">
      <img src="assets/laris-avatar.svg" alt="" width="56" height="56">
      <h3>Fale com a Laris</h3>
      <p>Nossa assistente virtual atende 24h, entende o que a sua empresa precisa e agenda a visita com o
      corretor da especialidade, aqui no site ou no Telegram.</p>
      <div class="service-actions">
        <button class="btn btn-outline" type="button" onclick="window.ImobiQ && ImobiQ.open()">Conversar agora</button>
        {telegram_link("btn btn-outline")}
      </div>
    </article>
  </div>
</section>

<section class="wrap block about" id="sobre">
  <div>
    <p class="eyebrow dark">Quem somos</p>
    <h2>Especialistas em imóveis corporativos</h2>
    <p>A Imobiliária Exemplo é uma consultoria fictícia de real estate: encontra a sede certa para cada empresa,
    o galpão ideal para cada operação e o imóvel locado certo para cada investidor. Nossa assistente virtual,
    a Laris, atende a qualquer hora, entende a necessidade e agenda a visita com o especialista.</p>
  </div>
  <dl class="stats">
    <div><dt>Imóveis na carteira</dt><dd>{len(props)}</dd></div>
    <div><dt>Locados para investidores</dt><dd>{leased}</dd></div>
    <div><dt>Atendimento</dt><dd>24h</dd></div>
  </dl>
</section>
"""
    return layout("Imóveis corporativos em São Paulo", body, widget, footer, active="home")


def listing(props: dict[str, dict], widget: str, footer: str) -> str:
    cards = "".join(card(p) for p in props.values())
    body = f"""
<section class="list-head">
  <div class="wrap">
    <form class="filters" id="filters" aria-label="Filtrar imóveis">
      <fieldset class="tabs tabs-dark">
        <legend class="sr-only">Pretensão</legend>
        <label><input type="radio" name="finalidade" value="" checked><span>Todos</span></label>
        <label><input type="radio" name="finalidade" value="aluguel"><span>Alugar</span></label>
        <label><input type="radio" name="finalidade" value="venda"><span>Comprar</span></label>
        <label><input type="radio" name="finalidade" value="investir"><span>Investir</span></label>
      </fieldset>
      <div class="search-row">
        <label class="field">Tipo de imóvel<select name="tipo"><option value="">Todos</option>
          {type_options(present_types(props))}</select></label>
        <label class="field grow">Onde<input name="q" list="places" autocomplete="off"
          placeholder="Digite edifício, região, bairro ou cidade"></label>
        <label class="field">Área mínima<select name="area"><option value="0">Qualquer</option>
          <option value="100">100 m²+</option><option value="500">500 m²+</option>
          <option value="1000">1.000 m²+</option><option value="5000">5.000 m²+</option>
          <option value="10000">10.000 m²+</option></select></label>
        <label class="field">Ordenar<select name="ordem"><option value="">Relevância</option>
          <option value="menor">Menor preço</option><option value="maior">Maior preço</option>
          <option value="area">Maior área</option></select></label>
      </div>
      <datalist id="places">{place_options(props)}</datalist>
    </form>
  </div>
</section>
<section class="wrap block">
  <p class="count"><span>Exibindo</span> <b id="count"></b></p>
  <div class="grid" id="results">{cards}</div>
  <p class="empty" id="empty" hidden>Nenhum imóvel com esses filtros.
    <button class="link-btn" type="button" data-laris="Quero encomendar um imóvel. Minha empresa procura ">
    Encomende com a Laris</button> e receba opções sob medida.</p>
</section>
<script src="assets/listing.js" defer></script>
"""
    return layout("Imóveis", body, widget, footer)


def detail(p: dict, props: dict[str, dict], widget: str, footer: str) -> str:
    f = p["features"]
    leased = f.get("locado")
    is_rent = p["purpose"] == "aluguel"

    costs = [("Aluguel" if is_rent else "Venda", brl(p["price"]) + ("/mês" if is_rent else ""))]
    if p["condo_fee"]:
        costs.append(("Condomínio", f"{brl(p['condo_fee'])}/mês"))
    if p["iptu"]:
        costs.append(("IPTU", f"{brl(p['iptu'])}/mês"))
    cost_rows = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in costs[1:])
    package = ""
    if is_rent and (p["condo_fee"] or p["iptu"]):
        total = p["price"] + (p["condo_fee"] or 0) + (p["iptu"] or 0)
        package = f'<div class="package"><dt>Pacote de locação</dt><dd>{brl(total)}/mês</dd></div>'

    area_label = "Área construída" if p["property_type"] == "galpão" else (
        "Área útil" if p["segment"] == "residencial" else "Área privativa")  # fmt: skip
    info = [(area_label, f"{num(p['area_m2'])} m²")]
    if p["segment"] == "residencial":
        info += [("Quartos", p["bedrooms"]), ("Suítes", p["suites"]), ("Banheiros", p["bathrooms"])]
    else:
        info.append(("Banheiros", p["bathrooms"]))
    info.append(("Vagas", p["parking"]))
    for key, label, fmt in (("edificio", "Edifício", str), ("condominio", "Condomínio logístico", str),
                            ("classe", "Classe", str), ("certificacao", "Certificação", str),
                            ("andar", "Andar", lambda v: f"{v}º"), ("andares", "Andares", str),
                            ("elevadores", "Elevadores", str), ("entrega", "Entrega", str),
                            ("pe_direito_m", "Pé-direito", lambda v: f"{num(v)} m"), ("docas", "Docas", str),
                            ("piso_carga_ton_m2", "Carga do piso", lambda v: f"{v} t/m²"),
                            ("acesso", "Acesso", str)):  # fmt: skip
        if f.get(key):
            info.append((label, fmt(f[key])))
    info_rows = "".join(f"<div><dt>{k}</dt><dd>{escape(str(v))}</dd></div>" for k, v in info)

    specs = list(p["amenities"]) + (["Perto do metrô"] if p["near_metro"] else [])
    spec_items = "".join(f"<li>{escape(s[0].upper() + s[1:])}</li>" for s in specs)
    activities = f.get("atividades", [])
    uses = (
        f'<h2 class="sec-title">Atividades permitidas</h2><ul class="chips">'
        f"{''.join(f'<li>{escape(a)}</li>' for a in activities)}</ul>"
        if activities
        else ""
    )
    leased_box = (
        f'<div class="leased-box"><p><b>Imóvel locado</b> para {escape(leased["inquilino"])}</p>'
        f"<p>Contrato até {leased['contrato_ate']} · aluguel atual de {brl(leased['aluguel_atual'])}/mês</p>"
        f"<p>Rentabilidade estimada de {num(p['estimated_yield'])}% ao ano (bruta, sem garantia)</p></div>"
        if leased
        else ""
    )
    similar = sorted(
        (o for o in props.values() if o["id"] != p["id"] and o["property_type"] == p["property_type"]
         and o["purpose"] == p["purpose"]),
        key=lambda o: abs(o["area_m2"] - p["area_m2"]),
    )[:3]  # fmt: skip
    similar_html = (
        f'<section class="wrap block"><div class="block-head"><h2>Imóveis semelhantes</h2></div>'
        f'<div class="grid">{"".join(card(o) for o in similar)}</div></section>'
        if similar
        else ""
    )
    action = "Falar sobre este investimento" if leased else "Agendar visita"
    message = f"Olá! Tenho interesse no imóvel código {p['id']}. Poderia me passar mais informações?"
    goal = "para investir" if leased else ("para alugar" if is_rent else "à venda")
    purpose_query = "investir" if leased else p["purpose"]
    purpose_label = "Investir" if leased else ("Alugar" if is_rent else "Comprar")
    body = f"""
<section class="wrap block detail-top">
  <nav class="crumbs" aria-label="Você está em">
    <a href="imoveis.html?finalidade={purpose_query}">{purpose_label}</a><span>|</span>
    <a href="imoveis.html?tipo={escape(p["property_type"])}">{escape(singular(p))}</a><span>|</span>
    <a href="imoveis.html?q={escape(p["city"])}">{escape(p["city"])}</a><span>|</span>
    <a href="imoveis.html?q={escape(p["neighborhood"])}">{escape(p["neighborhood"])}</a><span>|</span>
    <span>Imóvel {p["id"]}</span>
  </nav>
  <p class="code">{p["id"]}</p>
  <h1>{escape(headline(p))}</h1>
  {illustration(p, big=True)}
  <ul class="facts facts-big">{facts_html(p)}</ul>
  <div class="detail">
    <div class="detail-main">
      <h2 class="sec-title">Localização</h2>
      <p>{escape(location(p, " · "))}{" · perto do metrô" if p["near_metro"] else ""}</p>
      <h2 class="sec-title">Informações</h2>
      <dl class="spec-grid">{info_rows}</dl>
      <h2 class="sec-title">Descrição</h2>
      <p class="desc">{escape(p["description"])}</p>
      <h2 class="sec-title">Especificações técnicas</h2>
      <ul class="spec-list">{spec_items}</ul>
      {uses}
      <p class="fine-dark">Valores sujeitos a alteração. Imóvel e edifício fictícios, criados para demonstração.</p>
    </div>
    <aside class="box" aria-label="Valores e contato">
      <p class="box-type">{escape(singular(p))} {goal}</p>
      <p class="box-label">{costs[0][0]}</p>
      <p class="price big">{costs[0][1]}</p>
      <dl class="costs">{cost_rows}{package}</dl>
      {leased_box}
      <button class="btn btn-primary wide" type="button" onclick="window.ImobiQ && ImobiQ.open()">{action}</button>
      <form class="contact" data-laris-form aria-label="Fale com a imobiliária">
        <p class="contact-title">Fale com a imobiliária</p>
        <label class="sr-only" for="msg">Mensagem</label>
        <textarea id="msg" name="message" rows="3" maxlength="600">{escape(message)}</textarea>
        <button class="btn btn-outline wide" type="submit">Enviar mensagem</button>
        <p class="box-note">A mensagem abre no chat da Laris, que responde na hora e já sabe qual imóvel você
        está vendo.</p>
      </form>
    </aside>
  </div>
</section>
{similar_html}
"""
    return layout(headline(p), body, widget, footer, property_id=p["id"])


SITE_JS = """// comportamentos comuns: botões que abrem a Laris com mensagem pronta e busca por código
(function () {
  function laris(message) {
    if (window.ImobiQ) window.ImobiQ.open(message ? { message: message } : undefined);
  }
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-laris]");
    if (el) laris(el.getAttribute("data-laris"));
  });
  document.querySelectorAll("[data-laris-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      laris(form.elements.message.value.trim());
    });
  });
  var code = document.getElementById("code-search");
  if (code) {
    code.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = code.elements.code.value.trim().toUpperCase().replace(/^IMV-?/, "");
      if (/^\\d{1,3}$/.test(v)) location.href = "imovel-imv-" + ("00" + v).slice(-3) + ".html";
      else location.href = "imoveis.html?q=" + encodeURIComponent(code.elements.code.value);
    });
  }
})();
"""

LISTING_JS = """// filtros da listagem (sem backend): mostra/esconde e ordena os cards pelos atributos data-*
(function () {
  var TYPES = __TYPES__;
  var form = document.getElementById("filters");
  var grid = document.getElementById("results");
  var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));
  var count = document.getElementById("count");
  var empty = document.getElementById("empty");
  var params = new URLSearchParams(location.search);
  function norm(s) {
    return (s || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase().trim();
  }
  ["finalidade", "tipo", "q", "area", "ordem"].forEach(function (k) {
    var v = params.get(k);
    if (v === null) return;
    var el = form.elements[k];
    if (el instanceof RadioNodeList || el.length) {
      Array.prototype.forEach.call(form.querySelectorAll('[name="' + k + '"]'), function (r) {
        r.checked = r.value === v;
      });
    } else el.value = v;
  });
  function value(name) {
    var checked = form.querySelector('[name="' + name + '"]:checked');
    return checked ? checked.value : form.elements[name].value;
  }
  function apply() {
    var f = value("finalidade"), t = form.elements.tipo.value, q = norm(form.elements.q.value);
    var a = Number(form.elements.area.value), order = form.elements.ordem.value;
    var shown = 0;
    cards.forEach(function (c) {
      var purposeOk = !f || (f === "investir" ? c.dataset.leased === "1" : c.dataset.purpose === f);
      var ok = purposeOk && (!t || c.dataset.type === t) && Number(c.dataset.area) >= a &&
        (!q || norm(c.dataset.search).indexOf(q) !== -1);
      c.hidden = !ok;
      if (ok) shown++;
    });
    var sorted = cards.slice();
    if (order === "menor") sorted.sort(function (x, y) { return x.dataset.price - y.dataset.price; });
    if (order === "maior") sorted.sort(function (x, y) { return y.dataset.price - x.dataset.price; });
    if (order === "area") sorted.sort(function (x, y) { return y.dataset.area - x.dataset.area; });
    sorted.forEach(function (c) { grid.appendChild(c); });
    var noun = t ? TYPES[t] : "imóveis";
    var SUFFIX = { aluguel: " para alugar", venda: " à venda", investir: " locados para investir" };
    var suffix = SUFFIX[f] || "";
    count.textContent = shown + " " + noun.toLowerCase() + suffix;
    empty.hidden = shown > 0;
  }
  form.addEventListener("change", apply);
  form.addEventListener("input", apply);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  apply();
})();
"""

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="3" fill="#1e2237"/>
<rect x="4.5" y="4.5" width="23" height="23" rx="1.5" fill="none" stroke="#c9a45c" stroke-width="1.2"/>
<path d="M10 23V9M15 23V9h5M15 16h4M15 23h5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="square"/></svg>
"""


def build(widget: str) -> None:
    props = {p["id"]: p for p in json.loads(DATA.read_text(encoding="utf-8")) if p.get("available", True)}
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "style.css", DIST / "assets" / "style.css")
    plurals = json.dumps({t: v[1] for t, v in TYPES.items()}, ensure_ascii=False)
    (DIST / "assets" / "listing.js").write_text(LISTING_JS.replace("__TYPES__", plurals), encoding="utf-8")
    (DIST / "assets" / "site.js").write_text(SITE_JS, encoding="utf-8")
    (DIST / "assets" / "logo.svg").write_text(LOGO_SVG, encoding="utf-8")
    shutil.copy(ROOT.parent / "web" / "public" / "laris-avatar.svg", DIST / "assets" / "laris-avatar.svg")
    # favicons gerados do logo: .ico na raiz (todo navegador pede /favicon.ico) e ícone do iPhone (180 px)
    for icon in ("favicon.ico", "apple-touch-icon.png"):
        shutil.copy(ROOT / "icons" / icon, DIST / icon)
    footer = footer_html(props)
    (DIST / "index.html").write_text(home(props, widget, footer), encoding="utf-8")
    (DIST / "imoveis.html").write_text(listing(props, widget, footer), encoding="utf-8")
    for p in props.values():
        (DIST / page_name(p)).write_text(detail(p, props, widget, footer), encoding="utf-8")
    print(f"Site gerado em {DIST} ({len(props)} imóveis) · widget: {widget}")


def make_zip() -> Path:
    r"""Pacote para upload. Caminhos com "/" (padrão do formato zip): o Compress-Archive do Windows PowerShell 5.1
    grava "assets\style.css", e servidores Linux extraem isso como um arquivo com barra no nome, sem a pasta."""
    out = ROOT / "imobiliaria-exemplo.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST).as_posix())
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--widget", default="http://localhost:3001/widget.js", help="URL do widget.js da ImobiQ")
    parser.add_argument("--telegram", default=TELEGRAM, help="username do bot da Laris no Telegram ('' esconde)")
    parser.add_argument("--zip", action="store_true", help="gera também imobiliaria-exemplo.zip para upload")
    args = parser.parse_args()
    TELEGRAM = args.telegram
    build(args.widget)
    if args.zip:
        print(f"Pacote para upload: {make_zip()}")
