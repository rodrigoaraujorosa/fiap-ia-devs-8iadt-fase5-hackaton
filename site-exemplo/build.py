"""Gera o site estático da "Imobiliária Exemplo" (fictícia) com o widget da Laris embutido.

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

TYPE_LABEL = {"apartamento": "Apartamento", "casa": "Casa", "studio": "Studio", "cobertura": "Cobertura",
              "sala comercial": "Sala comercial"}  # fmt: skip
ZONE_HUE = {"zona sul": 200, "zona oeste": 160, "zona norte": 30, "zona leste": 280, "centro": 350}
FEATURED = ["IMV-007", "IMV-045", "IMV-056", "IMV-003", "IMV-058", "IMV-090"]


def brl(value: int | None) -> str:
    return f"R$ {value:,.0f}".replace(",", ".") if value else "—"


def price_label(p: dict) -> str:
    return f"{brl(p['price'])}<small>/mês</small>" if p["purpose"] == "aluguel" else brl(p["price"])


def page_name(p: dict) -> str:
    return f"imovel-{p['id'].lower()}.html"


# ---------------------------------------------------------------- ilustração (sem fotos: SVG por tipo de imóvel)

ICONS = {
    "casa": '<path d="M30 70V44l30-24 30 24v26" /><path d="M52 70V54h16v16" /><path d="M22 70h76" />',
    "apartamento": '<rect x="38" y="22" width="44" height="48" rx="2" /><path d="M46 32h8M66 32h8M46 44h8M66 44h8'
    'M46 56h8M66 56h8" /><path d="M24 70h72" />',
    "studio": '<rect x="34" y="30" width="52" height="40" rx="2" /><path d="M34 46h52" /><path d="M44 58h14v12H44z" />'
    '<path d="M24 70h72" />',
    "cobertura": '<rect x="40" y="30" width="40" height="40" rx="2" /><path d="M34 30h52l-6-10H40z" />'
    '<path d="M48 40h8M64 40h8M48 52h8M64 52h8" /><path d="M24 70h72" />',
    "sala comercial": '<rect x="30" y="26" width="60" height="44" rx="2" /><path d="M30 38h60" />'
    '<path d="M42 48h10v10H42zM58 48h20" /><path d="M24 70h72" />',
}


def illustration(p: dict, big: bool = False) -> str:
    hue = ZONE_HUE.get(p["zone"], 210)
    icon = ICONS.get(p["property_type"], ICONS["apartamento"])
    return (
        f'<div class="art{" art-big" if big else ""}" style="--h:{hue}">'
        f'<svg viewBox="0 0 120 90" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round">{icon}</g></svg>'
        f'<span class="tag">{"Aluguel" if p["purpose"] == "aluguel" else "Venda"}</span></div>'
    )


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
<meta name="description" content="Site fictício de imobiliária para demonstrar o widget da Laris (ImobiQ).">
<meta name="robots" content="noindex">
<link rel="icon" href="assets/logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<p class="demo-bar">Site fictício criado para demonstrar a integração com a <b>ImobiQ</b>. Os imóveis são simulados.</p>
<header class="top">
  <div class="wrap top-in">
    <a class="logo" href="index.html" aria-label="{BRAND}, página inicial">
      <img src="assets/logo.svg" alt="" width="34" height="34"><span>Imobiliária <b>Exemplo</b></span>
    </a>
    <nav aria-label="Principal">
      {nav("index.html", "Início", "home")}
      {nav("imoveis.html?finalidade=venda", "Comprar", "venda")}
      {nav("imoveis.html?finalidade=aluguel", "Alugar", "aluguel")}
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
    details = f"{p['bedrooms']} quarto{'s' if p['bedrooms'] != 1 else ''}" if p["bedrooms"] else "Studio"
    return (
        f'<article class="card" data-purpose="{p["purpose"]}" data-zone="{escape(p["zone"])}" '
        f'data-bedrooms="{p["bedrooms"]}" data-price="{p["price"]}">'
        f'<a href="{page_name(p)}">{illustration(p)}'
        f'<div class="card-body"><p class="where">{escape(p["neighborhood"])} · {escape(p["zone"])}</p>'
        f'<h3>{escape(p["title"])}</h3>'
        f'<p class="price">{price_label(p)}</p>'
        f'<p class="specs">{details} · {p["area_m2"]} m² · {p["parking"]} vaga{"s" if p["parking"] != 1 else ""}</p>'
        f"</div></a></article>"
    )


# ---------------------------------------------------------------- páginas


def home(props: dict[str, dict], widget: str) -> str:
    featured = "".join(card(props[code]) for code in FEATURED if code in props)
    zones = "".join(f'<option value="{z}">{z.title()}</option>' for z in ZONE_HUE)
    body = f"""
<section class="hero">
  <div class="wrap">
    <h1>Encontre seu lugar em São Paulo</h1>
    <p>Apartamentos, casas e studios para comprar, alugar ou investir, nos melhores bairros da cidade.</p>
    <form class="search" action="imoveis.html" method="get">
      <label>Quero<select name="finalidade"><option value="venda">Comprar</option>
        <option value="aluguel">Alugar</option></select></label>
      <label>Região<select name="zona"><option value="">Todas</option>{zones}</select></label>
      <button type="submit">Buscar imóveis</button>
    </form>
  </div>
</section>
<section class="wrap block">
  <div class="block-head"><h2>Destaques da semana</h2><a href="imoveis.html">Ver todos os imóveis →</a></div>
  <div class="grid">{featured}</div>
</section>
<section class="wrap block">
  <div class="laris">
    <div>
      <h2>Atendimento na hora, 24 horas por dia</h2>
      <p>A Laris, nossa assistente virtual, entende o que você procura, mostra imóveis que combinam com você e
      agenda sua visita com um corretor da região, tudo pelo chat.</p>
    </div>
    <button class="cta" type="button" onclick="window.ImobiQ && ImobiQ.open()">Conversar com a Laris</button>
  </div>
</section>
"""
    return layout("Imóveis em São Paulo", body, widget, active="home")


def listing(props: dict[str, dict], widget: str) -> str:
    cards = "".join(card(p) for p in props.values())
    zones = "".join(f'<option value="{z}">{z.title()}</option>' for z in ZONE_HUE)
    body = f"""
<section class="wrap block">
  <h1 class="page-title">Imóveis</h1>
  <form class="filters" id="filters" aria-label="Filtrar imóveis">
    <label>Finalidade<select name="finalidade"><option value="">Todas</option><option value="venda">Comprar</option>
      <option value="aluguel">Alugar</option></select></label>
    <label>Região<select name="zona"><option value="">Todas</option>{zones}</select></label>
    <label>Quartos<select name="quartos"><option value="0">Qualquer</option><option value="1">1+</option>
      <option value="2">2+</option><option value="3">3+</option></select></label>
  </form>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="grid" id="results">{cards}</div>
</section>
<script src="assets/listing.js" defer></script>
"""
    return layout("Imóveis", body, widget)


def detail(p: dict, widget: str) -> str:
    rows = [
        ("Quartos", p["bedrooms"] or "Studio"),
        ("Suítes", p["suites"]),
        ("Banheiros", p["bathrooms"]),
        ("Vagas", p["parking"]),
        ("Área", f"{p['area_m2']} m²"),
        ("Condomínio", brl(p["condo_fee"])),
        ("IPTU", brl(p["iptu"])),
    ]
    specs = "".join(f"<div><dt>{k}</dt><dd>{escape(str(v))}</dd></div>" for k, v in rows)
    perks = list(p["amenities"])
    perks += [label for flag, label in (("near_metro", "Perto do metrô"), ("pet_friendly", "Aceita pet"),
                                          ("furnished", "Mobiliado")) if p.get(flag)]  # fmt: skip
    chips = "".join(f"<li>{escape(a)}</li>" for a in perks)
    body = f"""
<section class="wrap block">
  <nav class="crumbs" aria-label="Você está em"><a href="index.html">Início</a> ›
    <a href="imoveis.html?finalidade={p["purpose"]}">{"Alugar" if p["purpose"] == "aluguel" else "Comprar"}</a> ›
    <span>{escape(p["neighborhood"])}</span></nav>
  <div class="detail">
    <div>
      {illustration(p, big=True)}
      <h1>{escape(p["title"])}</h1>
      <p class="where">{escape(p["neighborhood"])} · {escape(p["zone"])} · {escape(p["city"])} · código {p["id"]}</p>
      <p class="desc">{escape(p["description"])}</p>
      <dl class="spec-grid">{specs}</dl>
      <ul class="chips">{chips}</ul>
    </div>
    <aside class="box">
      <p class="box-type">{TYPE_LABEL.get(p["property_type"], p["property_type"])} para
        {"alugar" if p["purpose"] == "aluguel" else "comprar"}</p>
      <p class="price big">{price_label(p)}</p>
      <button class="cta wide" type="button" onclick="window.ImobiQ && ImobiQ.open()">Agendar uma visita</button>
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
  ["finalidade", "zona", "quartos"].forEach(function (k) {
    if (params.get(k)) form.elements[k].value = params.get(k);
  });
  function apply() {
    var f = form.elements.finalidade.value, z = form.elements.zona.value, q = Number(form.elements.quartos.value);
    var shown = 0;
    cards.forEach(function (c) {
      var ok = (!f || c.dataset.purpose === f) && (!z || c.dataset.zone === z) && Number(c.dataset.bedrooms) >= q;
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
<path d="M7 16.5 16 9l9 7.5" fill="none" stroke="#f4a261" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M10 15v8h12v-8" fill="none" stroke="#fff" stroke-width="2.4" stroke-linejoin="round"/></svg>
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
