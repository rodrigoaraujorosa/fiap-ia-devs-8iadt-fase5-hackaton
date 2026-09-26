"""Gera o site estático da "Imobiliária Exemplo" (fictícia, imóveis comerciais) com o widget da Laris embutido.

A base de imóveis é a mesma da ImobiQ (data/properties.json), então a Laris conhece cada imóvel do site.

Uso:
    python site-exemplo/build.py                                   # widget local (http://localhost:3001)
    python site-exemplo/build.py --widget https://imobiq.arrtsoftware.com.br/widget.js

Saída em site-exemplo/dist/ (é só subir essa pasta para qualquer hospedagem estática).
"""

import argparse
import json
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "properties.json"
DIST = ROOT / "dist"
BRAND = "Imobiliária Exemplo"

TYPES = {  # tipo: rótulo no plural (filtros e navegação)
    "sala comercial": "Salas e consultórios",
    "conjunto comercial": "Conjuntos comerciais",
    "laje corporativa": "Lajes corporativas",
    "loja": "Lojas e pontos",
    "galpão": "Galpões",
    "prédio comercial": "Prédios inteiros",
}
ZONE_HUE = {"zona sul": 200, "zona oeste": 160, "zona norte": 30, "zona leste": 280, "centro": 350, "grande sp": 100}
ZONE_LABEL = {"zona sul": "Zona Sul", "zona oeste": "Zona Oeste", "zona norte": "Zona Norte", "zona leste": "Zona Leste",
              "centro": "Centro", "grande sp": "Grande SP"}  # fmt: skip
FEATURED = ["IMV-021", "IMV-068", "IMV-051", "IMV-090", "IMV-063", "IMV-028"]


def brl(value: int | None) -> str:
    return f"R$ {value:,.0f}".replace(",", ".") if value else "—"


def num(value: float) -> str:
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


def price_label(p: dict) -> str:
    return f"{brl(p['price'])}<small>/mês</small>" if p["purpose"] == "aluguel" else brl(p["price"])


def page_name(p: dict) -> str:
    return f"imovel-{p['id'].lower()}.html"


def place(p: dict) -> str:
    region = ZONE_LABEL.get(p["zone"], p["zone"])
    if p["city"] != "São Paulo" and p["city"] != p["neighborhood"]:
        region = p["city"]
    return f"{p['neighborhood']} · {region}"


# ---------------------------------------------------------------- ilustração (sem fotos: SVG por tipo de imóvel)

ICONS = {
    "sala comercial": '<rect x="34" y="24" width="52" height="46" rx="2" /><path d="M42 34h36M42 44h36M42 54h14" />'
    '<path d="M24 70h72" />',
    "conjunto comercial": '<rect x="30" y="20" width="60" height="50" rx="2" /><path d="M38 30h10M56 30h10M74 30h8'
    'M38 42h10M56 42h10M74 42h8M38 54h10M56 54h10M74 54h8" /><path d="M22 70h76" />',
    "laje corporativa": '<path d="M44 70V14h32v56" /><path d="M50 22h20M50 30h20M50 38h20M50 46h20M50 54h20" />'
    '<path d="M32 70V40h12M76 34h12v36" /><path d="M22 70h76" />',
    "loja": '<path d="M28 34h64l-4-12H32z" /><path d="M30 34v36h60V34" /><path d="M40 70V48h16v22" />'
    '<rect x="62" y="46" width="18" height="12" rx="1" /><path d="M22 70h76" />',
    "galpão": '<path d="M22 70V38l38-18 38 18v32" /><path d="M36 70V50h14v20M56 70V50h14v20" />'
    '<path d="M76 56h12" /><path d="M16 70h88" />',
    "prédio comercial": '<rect x="38" y="16" width="44" height="54" rx="2" /><path d="M46 26h8M66 26h8M46 38h8M66 38h8'
    'M46 50h8M66 50h8" /><path d="M54 70V60h12v10" /><path d="M26 70h68" />',
}


def illustration(p: dict, big: bool = False) -> str:
    hue = ZONE_HUE.get(p["zone"], 210)
    icon = ICONS.get(p["property_type"], ICONS["sala comercial"])
    tag = "Locado · renda" if p["features"].get("locado") else ("Aluguel" if p["purpose"] == "aluguel" else "Venda")
    return (
        f'<div class="art{" art-big" if big else ""}" style="--h:{hue}">'
        f'<svg viewBox="0 0 120 90" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round">{icon}</g></svg>'
        f'<span class="tag">{tag}</span></div>'
    )


def key_spec(p: dict) -> str:
    """O atributo que mais importa em cada tipo (andar, docas, fachada...)."""
    f = p["features"]
    if f.get("docas"):
        return f"{f['docas']} docas · pé-direito {num(f['pe_direito_m'])} m"
    if f.get("fachada_m"):
        return f"{f['fachada_m']} m de frente"
    if f.get("andares"):
        return f"{f['andares']} andares"
    if f.get("andar"):
        return f"{f['andar']}º andar"
    return ""


# ---------------------------------------------------------------- blocos comuns


def layout(title: str, body: str, widget: str, property_id: str | None = None, active: str = "") -> str:
    data_property = f' data-property="{property_id}"' if property_id else ""

    def nav(href: str, label: str, key: str) -> str:
        current = ' aria-current="page"' if key == active else ""
        return f'<a href="{href}"{current}>{label}</a>'

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · {BRAND}</title>
<meta name="description" content="Site fictício de imobiliária comercial para demonstrar o widget da Laris (ImobiQ).">
<meta name="robots" content="noindex">
<link rel="icon" href="assets/logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<p class="demo-bar">Site fictício criado para demonstrar a integração com a <b>ImobiQ</b>. Os imóveis são simulados.</p>
<header class="top">
  <div class="wrap top-in">
    <a class="logo" href="index.html" aria-label="{BRAND}, página inicial">
      <img src="assets/logo.svg" alt="" width="34" height="34"><span>Imobiliária <b>Exemplo</b>
      <small>Imóveis comerciais</small></span>
    </a>
    <nav aria-label="Principal">
      {nav("index.html", "Início", "home")}
      {nav("imoveis.html?finalidade=aluguel", "Alugar", "aluguel")}
      {nav("imoveis.html?finalidade=venda", "Comprar", "venda")}
      {nav("imoveis.html?finalidade=investir", "Investir", "investir")}
      <a href="#contato">Contato</a>
    </nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="foot" id="contato">
  <div class="wrap foot-in">
    <div>
      <p class="logo"><img src="assets/logo.svg" alt="" width="28" height="28"><span>Imobiliária <b>Exemplo</b></span></p>
      <p>Av. Fictícia, 1000 · São Paulo, SP<br>Atendimento 24h com a Laris, nossa assistente virtual.</p>
    </div>
    <div>
      <p><b>Fale com a gente</b></p>
      <p><button class="link" type="button" onclick="window.ImobiQ && ImobiQ.open()">Conversar com a Laris</button></p>
    </div>
  </div>
  <p class="wrap fine">Imobiliária fictícia · demonstração do Hackathon FIAP Pós Tech · chat por ImobiQ</p>
</footer>
<script src="{widget}" data-brand="{BRAND}"{data_property} defer></script>
</body>
</html>
"""


def card(p: dict) -> str:
    parking = f"{p['parking']} vaga{'s' if p['parking'] != 1 else ''}" if p["parking"] else ""
    extras = [f"{num(p['area_m2'])} m²", key_spec(p), parking]
    leased = p["features"].get("locado")
    note = (
        f'<p class="leased">Locado para {escape(leased["inquilino"])} · {num(p["estimated_yield"])}% a.a.</p>'
        if leased
        else ""
    )
    return (
        f'<article class="card" data-purpose="{p["purpose"]}" data-type="{escape(p["property_type"])}" '
        f'data-zone="{escape(p["zone"])}" data-area="{p["area_m2"]}" data-leased="{1 if leased else 0}">'
        f'<a href="{page_name(p)}">{illustration(p)}'
        f'<div class="card-body"><p class="where">{escape(place(p))}</p>'
        f'<h3>{escape(p["title"])}</h3>'
        f'<p class="price">{price_label(p)}</p>'
        f'<p class="specs">{" · ".join(e for e in extras if e)}</p>{note}'
        f"</div></a></article>"
    )


def type_options() -> str:
    return "".join(f'<option value="{t}">{label}</option>' for t, label in TYPES.items())


def zone_options() -> str:
    return "".join(f'<option value="{z}">{label}</option>' for z, label in ZONE_LABEL.items())


# ---------------------------------------------------------------- páginas


def home(props: dict[str, dict], widget: str) -> str:
    featured = "".join(card(props[code]) for code in FEATURED if code in props)
    counts = {t: sum(p["property_type"] == t for p in props.values()) for t in TYPES}
    tiles = "".join(
        f'<a class="tile" href="imoveis.html?tipo={escape(t)}"><b>{label}</b><span>{counts[t]} imóveis</span></a>'
        for t, label in TYPES.items()
    )
    body = f"""
<section class="hero">
  <div class="wrap">
    <h1>O espaço certo para o seu negócio em São Paulo</h1>
    <p>Salas, escritórios, lojas e galpões para alugar ou comprar, e imóveis já locados para quem quer investir.</p>
    <form class="search" action="imoveis.html" method="get">
      <label>Quero<select name="finalidade"><option value="aluguel">Alugar</option><option value="venda">Comprar</option>
        <option value="investir">Investir (imóvel locado)</option></select></label>
      <label>Tipo<select name="tipo"><option value="">Todos</option>{type_options()}</select></label>
      <label>Região<select name="zona"><option value="">Todas</option>{zone_options()}</select></label>
      <button type="submit">Buscar imóveis</button>
    </form>
  </div>
</section>
<section class="wrap block">
  <div class="tiles">{tiles}</div>
</section>
<section class="wrap block">
  <div class="block-head"><h2>Destaques da semana</h2><a href="imoveis.html">Ver todos os imóveis →</a></div>
  <div class="grid">{featured}</div>
</section>
<section class="wrap block">
  <div class="laris">
    <div>
      <h2>Atendimento na hora, 24 horas por dia</h2>
      <p>A Laris, nossa assistente virtual, entende a necessidade da sua empresa (atividade, tamanho, região e
      orçamento), mostra os imóveis que fazem sentido e agenda a visita com o corretor especialista, tudo pelo chat.</p>
    </div>
    <button class="cta" type="button" onclick="window.ImobiQ && ImobiQ.open()">Conversar com a Laris</button>
  </div>
</section>
"""
    return layout("Imóveis comerciais em São Paulo", body, widget, active="home")


def listing(props: dict[str, dict], widget: str) -> str:
    cards = "".join(card(p) for p in props.values())
    body = f"""
<section class="wrap block">
  <h1 class="page-title">Imóveis comerciais</h1>
  <form class="filters" id="filters" aria-label="Filtrar imóveis">
    <label>Finalidade<select name="finalidade"><option value="">Todas</option><option value="aluguel">Alugar</option>
      <option value="venda">Comprar</option><option value="investir">Investir (locado)</option></select></label>
    <label>Tipo<select name="tipo"><option value="">Todos</option>{type_options()}</select></label>
    <label>Região<select name="zona"><option value="">Todas</option>{zone_options()}</select></label>
    <label>Área mínima<select name="area"><option value="0">Qualquer</option><option value="50">50 m²+</option>
      <option value="200">200 m²+</option><option value="1000">1.000 m²+</option>
      <option value="3000">3.000 m²+</option></select></label>
  </form>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="grid" id="results">{cards}</div>
</section>
<script src="assets/listing.js" defer></script>
"""
    return layout("Imóveis", body, widget)


def detail(p: dict, widget: str) -> str:
    f = p["features"]
    rows = [("Área", f"{num(p['area_m2'])} m²"), ("Vagas", p["parking"]), ("Banheiros", p["bathrooms"])]
    if f.get("andar"):
        rows.append(("Andar", f"{f['andar']}º"))
    if f.get("andares"):
        rows.append(("Andares", f["andares"]))
    if f.get("pe_direito_m"):
        rows.append(("Pé-direito", f"{num(f['pe_direito_m'])} m"))
    if f.get("docas"):
        rows.append(("Docas", f["docas"]))
    if f.get("piso_carga_ton_m2"):
        rows.append(("Carga do piso", f"{f['piso_carga_ton_m2']} t/m²"))
    if f.get("fachada_m"):
        rows.append(("Fachada", f"{f['fachada_m']} m"))
    if f.get("acesso"):
        rows.append(("Acesso", f["acesso"]))
    rows += [("Condomínio", brl(p["condo_fee"])), ("IPTU", brl(p["iptu"]))]
    specs = "".join(f"<div><dt>{k}</dt><dd>{escape(str(v))}</dd></div>" for k, v in rows)
    perks = list(p["amenities"]) + (["Perto do metrô"] if p["near_metro"] else [])
    chips = "".join(f"<li>{escape(a)}</li>" for a in perks)
    activities = ", ".join(f.get("atividades", []))
    leased = f.get("locado")
    leased_box = (
        f'<div class="leased-box"><p><b>Imóvel locado</b> para {escape(leased["inquilino"])}</p>'
        f"<p>Contrato até {leased['contrato_ate']} · aluguel atual de {brl(leased['aluguel_atual'])}/mês</p>"
        f"<p>Rentabilidade estimada de {num(p['estimated_yield'])}% ao ano (bruta, sem garantia)</p></div>"
        if leased
        else ""
    )
    action = "Falar sobre este investimento" if leased else "Agendar uma visita"
    purpose_label = "Investir" if leased else ("Alugar" if p["purpose"] == "aluguel" else "Comprar")
    purpose_query = "investir" if leased else p["purpose"]
    body = f"""
<section class="wrap block">
  <nav class="crumbs" aria-label="Você está em"><a href="index.html">Início</a> ›
    <a href="imoveis.html?finalidade={purpose_query}">{purpose_label}</a> ›
    <span>{escape(p["neighborhood"])}</span></nav>
  <div class="detail">
    <div>
      {illustration(p, big=True)}
      <h1>{escape(p["title"])}</h1>
      <p class="where">{escape(place(p))} · código {p["id"]}</p>
      <p class="desc">{escape(p["description"])}</p>
      <dl class="spec-grid">{specs}</dl>
      <p class="allowed"><b>Atividades permitidas:</b> {escape(activities)}</p>
      <ul class="chips">{chips}</ul>
    </div>
    <aside class="box">
      <p class="box-type">{escape(p["property_type"].capitalize())} para
        {"investir" if leased else ("alugar" if p["purpose"] == "aluguel" else "comprar")}</p>
      <p class="price big">{price_label(p)}</p>
      {leased_box}
      <button class="cta wide" type="button" onclick="window.ImobiQ && ImobiQ.open()">{action}</button>
      <p class="box-note">A Laris responde na hora e já sabe que você está vendo este imóvel.</p>
    </aside>
  </div>
</section>
"""
    return layout(p["title"], body, widget, property_id=p["id"])


LISTING_JS = """// filtros da listagem (sem backend): mostra/esconde os cards pelos atributos data-*
(function () {
  var form = document.getElementById("filters");
  var cards = Array.prototype.slice.call(document.querySelectorAll("#results .card"));
  var count = document.getElementById("count");
  var params = new URLSearchParams(location.search);
  ["finalidade", "tipo", "zona", "area"].forEach(function (k) {
    if (params.get(k)) form.elements[k].value = params.get(k);
  });
  function apply() {
    var f = form.elements.finalidade.value, t = form.elements.tipo.value, z = form.elements.zona.value;
    var a = Number(form.elements.area.value);
    var shown = 0;
    cards.forEach(function (c) {
      var purposeOk = !f || (f === "investir" ? c.dataset.leased === "1" : c.dataset.purpose === f);
      var ok = purposeOk && (!t || c.dataset.type === t) && (!z || c.dataset.zone === z) && Number(c.dataset.area) >= a;
      c.hidden = !ok;
      if (ok) shown++;
    });
    count.textContent = shown + (shown === 1 ? " imóvel encontrado" : " imóveis encontrados");
  }
  form.addEventListener("change", apply);
  apply();
})();
"""

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e3a5f"/>
<path d="M9 24V11h8v13M17 24V7h6v17" fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/>
<path d="M6 24h20" stroke="#f4a261" stroke-width="2.6" stroke-linecap="round"/></svg>
"""


def build(widget: str) -> None:
    props = {p["id"]: p for p in json.loads(DATA.read_text(encoding="utf-8")) if p.get("available", True)}
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "style.css", DIST / "assets" / "style.css")
    (DIST / "assets" / "listing.js").write_text(LISTING_JS, encoding="utf-8")
    (DIST / "assets" / "logo.svg").write_text(LOGO_SVG, encoding="utf-8")
    (DIST / "index.html").write_text(home(props, widget), encoding="utf-8")
    (DIST / "imoveis.html").write_text(listing(props, widget), encoding="utf-8")
    for p in props.values():
        (DIST / page_name(p)).write_text(detail(p, widget), encoding="utf-8")
    print(f"Site gerado em {DIST} ({len(props)} imóveis) · widget: {widget}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--widget", default="http://localhost:3001/widget.js", help="URL do widget.js da ImobiQ")
    build(parser.parse_args().widget)
