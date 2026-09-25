/*!
 * Widget da Laris (ImobiQ) — chat de pré-atendimento para sites de imobiliárias.
 *
 * Instalação (uma linha, antes de </body>):
 *   <script src="https://SEU-APP/widget.js" data-brand="Nome da Imobiliária" defer></script>
 *
 * Atributos opcionais:
 *   data-property="IMV-007"   imóvel da página (a Laris já abre falando dele)
 *   data-teaser-delay="8"     segundos até o convite aparecer (0 desliga)
 *   data-position="left"      canto da tela (padrão: direita)
 *
 * API: window.ImobiQ.open() · .close() · .toggle()
 */
(function () {
  "use strict";
  if (window.ImobiQ && window.ImobiQ.__loaded) return;

  var script = document.currentScript;
  if (!script) return;
  var APP = new URL(script.src).origin;
  var cfg = {
    brand: script.dataset.brand || "",
    property: (script.dataset.property || "").toUpperCase(),
    teaserDelay: script.dataset.teaserDelay === undefined ? 8 : Number(script.dataset.teaserDelay),
    left: script.dataset.position === "left",
  };
  var LEAD_KEY = "imobiq:widget:lead";
  var UTM_KEY = "imobiq:widget:utm";
  var TEASER_KEY = "imobiq:widget:teaser-dismissed";

  // ------------------------------------------------------------ armazenamento (pode falhar: modo privado etc.)
  function read(storage, key) {
    try {
      return window[storage].getItem(key);
    } catch (e) {
      return null;
    }
  }
  function write(storage, key, value) {
    try {
      if (value === null) window[storage].removeItem(key);
      else window[storage].setItem(key, value);
    } catch (e) {
      /* sem armazenamento: a conversa só não é retomada */
    }
  }

  // UTM de primeiro toque: guardada na chegada ao site, vale para a sessão inteira
  var utm = {};
  try {
    utm = JSON.parse(read("sessionStorage", UTM_KEY) || "{}");
  } catch (e) {
    utm = {};
  }
  var query = new URLSearchParams(location.search);
  ["utm_source", "utm_medium", "utm_campaign"].forEach(function (k) {
    if (query.get(k) && !utm[k]) utm[k] = query.get(k);
  });
  write("sessionStorage", UTM_KEY, JSON.stringify(utm));

  // ------------------------------------------------------------ interface (Shadow DOM isola o CSS do site)
  var host = document.createElement("div");
  host.id = "imobiq-widget";
  var root = host.attachShadow({ mode: "open" });
  var side = cfg.left ? "left" : "right";
  root.innerHTML =
    "<style>" +
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}" +
    ".launcher{position:fixed;bottom:20px;" + side + ":20px;z-index:2147483646;width:60px;height:60px;border:0;" +
    "border-radius:50%;padding:0;cursor:pointer;background:transparent;box-shadow:0 8px 24px rgba(15,23,42,.28);" +
    "transition:transform .15s ease}" +
    ".launcher:hover{transform:scale(1.06)}" +
    ".launcher:focus-visible{outline:3px solid #14b8a6;outline-offset:3px}" +
    ".launcher svg{display:block;width:60px;height:60px}" +
    ".launcher .close{display:none}.launcher.is-open .chat{display:none}.launcher.is-open .close{display:block}" +
    ".teaser{position:fixed;bottom:92px;" + side + ":20px;z-index:2147483646;max-width:280px;background:#fff;" +
    "color:#1f2933;border-radius:14px;padding:12px 34px 12px 14px;font-size:14px;line-height:1.4;" +
    "box-shadow:0 8px 30px rgba(15,23,42,.18);cursor:pointer;animation:pop .25s ease}" +
    ".teaser b{color:#0f766e}" +
    ".teaser .x{position:absolute;top:6px;right:6px;width:24px;height:24px;border:0;background:none;color:#6b7280;" +
    "font-size:18px;line-height:1;cursor:pointer;border-radius:6px}" +
    ".teaser .x:hover{background:#f3f4f6}" +
    ".panel{position:fixed;bottom:92px;" + side + ":20px;z-index:2147483647;width:390px;height:min(640px,calc(100vh - 120px));" +
    "border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 16px 48px rgba(15,23,42,.3);" +
    "opacity:0;transform:translateY(12px);pointer-events:none;transition:opacity .18s ease,transform .18s ease}" +
    ".panel.open{opacity:1;transform:none;pointer-events:auto}" +
    ".panel iframe{width:100%;height:100%;border:0;display:block}" +
    "@media (max-width:640px){.panel{inset:0;width:100%;height:100%;border-radius:0;bottom:0}" +
    ".panel.open~.launcher{display:none}}" +
    "@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}" +
    "@media (prefers-reduced-motion:reduce){.launcher,.panel{transition:none}.teaser{animation:none}}" +
    "</style>" +
    '<div class="panel" role="dialog" aria-label="Chat com a Laris" aria-hidden="true"></div>' +
    '<button class="launcher" type="button" aria-label="Abrir chat com a Laris" aria-expanded="false">' +
    '<svg class="close" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="18" fill="#0f766e"/>' +
    '<path d="m12.5 12.5 11 11m0-11-11 11" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/></svg>' +
    '<svg class="chat" viewBox="0 0 36 36" aria-hidden="true"><defs><linearGradient id="g" x1="0" y1="0" x2="36" y2="36" ' +
    'gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#14b8a6"/><stop offset="1" stop-color="#0f766e"/>' +
    '</linearGradient></defs><circle cx="18" cy="18" r="18" fill="url(#g)"/>' +
    '<path d="M11 10.5h14a3 3 0 0 1 3 3v7.5a3 3 0 0 1-3 3h-7.5l-4.5 3.8v-3.8H11a3 3 0 0 1-3-3v-7.5a3 3 0 0 1 3-3z" fill="#fff"/>' +
    '<path d="m13.8 19.4 4.2-3.6 4.2 3.6" fill="none" stroke="#0f766e" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"/></svg></button>';

  var panel = root.querySelector(".panel");
  var launcher = root.querySelector(".launcher");
  var teaser = null;
  var iframe = null;
  var isOpen = false;

  function iframeUrl() {
    var params = new URLSearchParams({
      host: location.origin,
      brand: cfg.brand,
      page_url: location.href,
      page_title: document.title,
      referrer: document.referrer,
    });
    if (cfg.property) params.set("property", cfg.property);
    var lead = read("localStorage", LEAD_KEY);
    if (lead) params.set("lead", lead);
    Object.keys(utm).forEach(function (k) {
      params.set(k, utm[k]);
    });
    return APP + "/embed?" + params.toString();
  }

  function open() {
    if (isOpen) return;
    hideTeaser(true);
    if (!iframe) {
      // o chat só é carregado no primeiro clique: não pesa no carregamento do site
      iframe = document.createElement("iframe");
      iframe.title = "Chat com a Laris";
      iframe.src = iframeUrl();
      iframe.allow = "clipboard-write";
      panel.appendChild(iframe);
    }
    isOpen = true;
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    launcher.setAttribute("aria-expanded", "true");
    launcher.classList.add("is-open");
    launcher.setAttribute("aria-label", "Fechar chat com a Laris");
    setTimeout(function () {
      iframe.focus();
    }, 150);
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    launcher.setAttribute("aria-expanded", "false");
    launcher.classList.remove("is-open");
    launcher.setAttribute("aria-label", "Abrir chat com a Laris");
    launcher.focus();
  }

  function toggle() {
    if (isOpen) close();
    else open();
  }

  function hideTeaser(remember) {
    if (teaser) {
      teaser.remove();
      teaser = null;
    }
    if (remember) write("sessionStorage", TEASER_KEY, "1");
  }

  function showTeaser() {
    if (isOpen || teaser || read("sessionStorage", TEASER_KEY)) return;
    teaser = document.createElement("div");
    teaser.className = "teaser";
    teaser.setAttribute("role", "status");
    var text = cfg.property
      ? "Oi! Sou a <b>Laris</b>. Quer saber mais sobre este imóvel ou agendar uma visita?"
      : "Oi! Sou a <b>Laris</b>. Posso te ajudar a encontrar o imóvel ideal?";
    teaser.innerHTML = text + '<button class="x" type="button" aria-label="Dispensar convite">×</button>';
    teaser.addEventListener("click", function (e) {
      if (e.target.classList.contains("x")) hideTeaser(true);
      else open();
    });
    root.appendChild(teaser);
  }

  launcher.addEventListener("click", toggle);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen) close();
  });

  // mensagens do chat (iframe): só aceita as que vêm da origem do app
  window.addEventListener("message", function (e) {
    if (e.origin !== APP || !e.data || typeof e.data !== "object") return;
    if (e.data.type === "imobiq:lead") write("localStorage", LEAD_KEY, e.data.id || null);
    if (e.data.type === "imobiq:close") close();
  });

  function mount() {
    document.body.appendChild(host);
    if (cfg.teaserDelay > 0) setTimeout(showTeaser, cfg.teaserDelay * 1000);
  }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);

  window.ImobiQ = { __loaded: true, open: open, close: close, toggle: toggle };
})();
