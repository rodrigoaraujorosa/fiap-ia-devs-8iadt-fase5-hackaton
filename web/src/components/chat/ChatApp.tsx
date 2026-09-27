"use client";

import { BellRing, CalendarCheck, Headset, RotateCcw, Send, SendHorizontal, UserRound, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { LarisAvatar } from "@/components/Brand";
import { LeadPanel, type Analysis, type AppointmentInfo } from "@/components/chat/LeadPanel";
import { PropertyCard } from "@/components/PropertyCard";
import { Markdown } from "@/components/ui";
import {
  ApiError,
  apiGet,
  apiPost,
  streamChat,
  type ChatEvent,
  type Lead,
  type LeadDetail,
  type LeadSource,
  type Property,
  type TelegramAvailability,
} from "@/lib/api";
import { TOOL_ACTIVITY, brl, clockTime, dateTime } from "@/lib/format";

/** Chat dentro do widget (site de uma imobiliária): a sessão é guardada pela página que hospeda o widget. */
export type EmbedOptions = {
  brand: string;
  leadId: string | null;
  hostOrigin: string | null; // origem da página hospedeira, destino das mensagens postMessage
  source: LeadSource;
  draft?: string; // mensagem pré-preenchida pelo site (ImobiQ.open({ message })): o visitante revisa e envia
};

type UiMessage = {
  key: string;
  serverId?: number;
  role: "user" | "assistant" | "followup";
  content: string;
  at: string;
  properties?: Property[];
  appointment?: AppointmentInfo;
  handoff?: { corretor: string; prazo_retorno: string };
  streaming?: boolean;
};

export const CHAT_STORAGE_KEY = "imobiq:lead_id";
const WELCOME =
  "Oi! Eu sou a Laris, da ImobiQ 😊 Posso te ajudar a encontrar um espaço para a sua empresa (conjunto, andar corporativo, prédio ou galpão) ou um imóvel comercial para investir. Me conta o que você procura?";
const SUGGESTIONS = [
  "Procuro um conjunto para a minha clínica na zona sul.",
  "Quero investir em imóveis comerciais para renda.",
  "Preciso de um galpão perto da Via Dutra.",
];
const POLL_MS = 5000;
const PAUSED_WELCOME =
  "Oi! Nosso atendimento automático está pausado no momento 😊 Deixe seu nome e telefone abaixo que um corretor retorna.";

function embedWelcome(brand: string, property: Property | null): string {
  if (!property) {
    return `Oi! Eu sou a Laris, assistente virtual da ${brand} 😊 Posso te ajudar a encontrar um espaço para a sua empresa ou um imóvel comercial para investir. Me conta o que você procura?`;
  }
  const price = property.purpose === "aluguel" ? `${brl(property.price)}/mês` : brl(property.price);
  return `Oi! Eu sou a Laris, assistente virtual da ${brand} 😊 Vi que você está olhando o ${property.title} (${price}). Quer saber mais sobre ele, ver opções parecidas ou agendar uma visita?`;
}

function embedSuggestions(property: Property | null): string[] {
  if (!property) return SUGGESTIONS;
  return ["Quero agendar uma visita", "Me conta mais sobre este imóvel", "Tem outros parecidos?"];
}

const propertyCache = new Map<string, Property>();
async function loadProperties(ids: string[] = []): Promise<Property[]> {
  const missing = ids.filter((id) => !propertyCache.has(id));
  await Promise.all(
    missing.map(async (id) => {
      try {
        propertyCache.set(id, await apiGet<Property>(`/properties/${id}`));
      } catch {
        /* imóvel removido: ignora */
      }
    }),
  );
  return ids.map((id) => propertyCache.get(id)).filter((p): p is Property => Boolean(p));
}

function upcomingAppointment(detail: LeadDetail): AppointmentInfo | null {
  const appt = detail.appointments.find(
    (a) => ["agendado", "confirmado"].includes(a.status) && new Date(a.start_at) > new Date(),
  );
  return appt
    ? { tipo: appt.kind, quando: dateTime(appt.start_at), com: appt.broker.name, imovel: appt.property_id }
    : null;
}

export function ChatApp({ embed }: { embed?: EmbedOptions } = {}) {
  const [leadId, setLeadId] = useState<string | null>(() => {
    if (embed) return embed.leadId;
    return typeof window === "undefined" ? null : window.localStorage.getItem(CHAT_STORAGE_KEY);
  });
  const [pageProperty, setPageProperty] = useState<Property | null>(null);
  const leadIdRef = useRef(leadId);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [lead, setLead] = useState<Lead | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [agent, setAgent] = useState<string | null>(null);
  const [appointment, setAppointment] = useState<AppointmentInfo | null>(null);
  const [input, setInput] = useState(embed?.draft ?? "");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [telegram, setTelegram] = useState<TelegramAvailability | null>(null);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastServerId = useRef<number | null>(null);
  const busyRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // --------------------------------------------------------------- sincronização com a API
  const syncFromServer = useCallback(async (id: string) => {
    const detail = await apiGet<LeadDetail>(`/leads/${id}`);
    const last = detail.messages.at(-1)?.id ?? null;
    if (busyRef.current) return;
    setLead(detail);
    setAppointment(upcomingAppointment(detail));
    setAnalysis((a) => ({ route: a?.route ?? "", missing: detail.missing }));
    if (last === lastServerId.current) return;
    lastServerId.current = last;
    const rebuilt: UiMessage[] = await Promise.all(
      detail.messages
        .filter((m) => m.role !== "system")
        .map(async (m) => ({
          key: `s-${m.id}`,
          serverId: m.id,
          role: m.role as UiMessage["role"],
          content: m.content,
          at: m.created_at,
          properties: await loadProperties(m.meta?.property_ids),
          appointment: m.meta?.appointment,
          handoff: m.meta?.handoff,
        })),
    );
    if (!busyRef.current) setMessages(rebuilt);
    const lastAgent = [...detail.messages].reverse().find((m) => m.role === "assistant")?.agent;
    if (lastAgent) setAgent(lastAgent);
  }, []);

  // guarda a sessão: no app, no localStorage; no widget, avisa a página hospedeira (que guarda no domínio dela)
  const saveLeadId = useCallback(
    (id: string | null) => {
      leadIdRef.current = id;
      setLeadId(id);
      if (embed) {
        if (embed.hostOrigin) window.parent.postMessage({ type: "imobiq:lead", id }, embed.hostOrigin);
        return;
      }
      if (id) window.localStorage.setItem(CHAT_STORAGE_KEY, id);
      else window.localStorage.removeItem(CHAT_STORAGE_KEY);
    },
    [embed],
  );

  // retoma a conversa salva (localStorage no app; parâmetro da página hospedeira no widget)
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !leadId) return;
    restored.current = true;
    syncFromServer(leadId).catch(() => saveLeadId(null));
  }, [leadId, syncFromServer, saveLeadId]);

  // no widget, o foco fica dentro do iframe: o Esc precisa ser repassado ao site para fechar o chat
  useEffect(() => {
    const host = embed?.hostOrigin;
    if (!host) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") window.parent.postMessage({ type: "imobiq:close" }, host);
    };
    window.addEventListener("keydown", onKey);
    // o site pode abrir o chat com uma mensagem pronta (ex.: formulário "Fale com a imobiliária")
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== host || e.data?.type !== "imobiq:draft" || typeof e.data.text !== "string") return;
      setInput(e.data.text.slice(0, 2000));
      inputRef.current?.focus();
    };
    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("message", onMessage);
    };
  }, [embed?.hostOrigin]);

  // IA pausada nas configurações: a Laris não conversa; o chat pede nome e telefone num formulário
  useEffect(() => {
    apiGet<{ ai_enabled: boolean }>("/chat/status")
      .then((s) => setAiEnabled(s.ai_enabled))
      .catch(() => {});
  }, []);

  async function sendContact(name: string, phone: string) {
    let id = leadIdRef.current;
    if (!id) {
      const created = await apiPost<Lead>("/chat/sessions", embed ? { source: embed.source } : {});
      id = created.id;
      saveLeadId(id);
    }
    setLead(await apiPost<Lead>(`/chat/${id}/contact`, { name, phone }));
    lastServerId.current = null;
    await syncFromServer(id);
  }

  // bot do Telegram disponível? (botão "Continuar no Telegram")
  useEffect(() => {
    apiGet<TelegramAvailability>("/chat/telegram")
      .then(setTelegram)
      .catch(() => setTelegram(null));
  }, []);

  async function continueOnTelegram() {
    if (!telegram?.link) return;
    const tab = window.open("", "_blank"); // abre no clique: navegadores bloqueiam pop-up aberto depois de um await
    let url = telegram.link;
    const id = leadIdRef.current;
    if (id) {
      try {
        url = (await apiPost<{ url: string }>(`/chat/${id}/telegram-link`)).url; // leva a conversa junto
      } catch {
        /* sem vínculo: abre o bot numa conversa nova */
      }
    }
    if (tab) {
      tab.opener = null;
      tab.location.href = url;
    } else {
      window.location.href = url;
    }
  }

  // widget na página de um imóvel: carrega o imóvel para a saudação personalizada
  const pagePropertyId = embed?.source.property_id;
  useEffect(() => {
    if (!pagePropertyId) return;
    loadProperties([pagePropertyId]).then(([p]) => setPageProperty(p ?? null));
  }, [pagePropertyId]);

  // follow-ups chegam sem o lead ter escrito: consulta periódica enquanto ocioso
  useEffect(() => {
    if (!leadId) return;
    const timer = window.setInterval(() => {
      if (!busyRef.current) syncFromServer(leadId).catch(() => {});
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [leadId, syncFromServer]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, activity]);

  // --------------------------------------------------------------- envio com streaming
  const patchLast = (patch: (m: UiMessage) => UiMessage) =>
    setMessages((list) => list.map((m, i) => (i === list.length - 1 ? patch(m) : m)));

  function handleEvent(event: ChatEvent) {
    switch (event.type) {
      case "analysis":
        setAnalysis({ route: event.route, missing: event.missing });
        setLead((l) => (l ? { ...l, score: event.score, temperature: event.temperature, status: event.status, intent: event.intent } : l));
        break;
      case "agent":
        setAgent(event.agent);
        break;
      case "token":
        setActivity(null);
        patchLast((m) => ({ ...m, content: m.content + event.text }));
        break;
      case "bubble": {
        // texto novo depois de uma ferramenta: outro balão, como no WhatsApp
        const at = new Date().toISOString();
        setMessages((list) => [
          ...list.map((m, i) => (i === list.length - 1 ? { ...m, streaming: false } : m)),
          { key: `a-${at}-${list.length}`, role: "assistant", content: "", at, streaming: true },
        ]);
        break;
      }
      case "tool":
        setActivity(event.status === "start" ? (TOOL_ACTIVITY[event.name] ?? "pensando") : null);
        break;
      case "properties":
        // só guarda: os cards exibidos são os imóveis citados na resposta final (evento "done")
        event.items.forEach((p) => propertyCache.set(p.id, p));
        break;
      case "appointment": {
        const info = { tipo: event.tipo, quando: event.quando, com: event.com, imovel: event.imovel };
        setAppointment(info);
        patchLast((m) => ({ ...m, appointment: info }));
        break;
      }
      case "handoff":
        patchLast((m) => ({ ...m, handoff: { corretor: event.corretor, prazo_retorno: event.prazo_retorno } }));
        break;
      case "error":
        setError(event.message);
        break;
      case "done":
        setLead(event.lead);
        if (event.contact_form !== undefined || event.agent) setAiEnabled(!event.contact_form && Boolean(event.agent));
        patchLast((m) => ({
          ...m,
          content: event.bubbles.at(-1) || m.content,
          properties: event.property_ids.map((id) => propertyCache.get(id)).filter((p): p is Property => Boolean(p)),
          streaming: false,
        }));
        break;
    }
  }

  async function send(text: string) {
    const content = text.trim();
    if (!content || busyRef.current) return;
    setError(null);
    setInput("");
    busyRef.current = true;
    setBusy(true);
    setActivity("lendo sua mensagem");
    const now = new Date().toISOString();
    setMessages((list) => [
      ...list,
      { key: `u-${now}`, role: "user", content, at: now },
      { key: `a-${now}`, role: "assistant", content: "", at: now, streaming: true },
    ]);
    try {
      let id = leadIdRef.current;
      if (!id) {
        const created = await apiPost<Lead>("/chat/sessions", embed ? { source: embed.source } : {});
        id = created.id;
        saveLeadId(id);
        setLead(created);
      }
      const context = embed ? { page_url: embed.source.page_url, property_id: embed.source.property_id } : undefined;
      await streamChat(id, content, handleEvent, context);
    } catch {
      setError("Não consegui falar com o servidor. Verifique se a API está no ar e tente de novo.");
      setMessages((list) => list.filter((m) => !(m.streaming && !m.content)));
    } finally {
      busyRef.current = false;
      setBusy(false);
      setActivity(null);
      patchLast((m) => ({ ...m, streaming: false }));
      if (leadIdRef.current) {
        lastServerId.current = null; // força ressincronizar ids e horários do servidor
        syncFromServer(leadIdRef.current).catch(() => {});
      }
    }
  }

  function reset() {
    lastServerId.current = null;
    saveLeadId(null);
    setMessages([]);
    setLead(null);
    setAnalysis(null);
    setAgent(null);
    setAppointment(null);
    setError(null);
  }

  // --------------------------------------------------------------- render
  const welcome = !aiEnabled ? PAUSED_WELCOME : embed ? embedWelcome(embed.brand, pageProperty) : WELCOME;
  const askContact = !aiEnabled && !busy && !(lead?.name && lead?.phone);
  const suggestions = embed ? embedSuggestions(pageProperty) : SUGGESTIONS;
  const chat = (
      <section
        className={
          embed
            ? "flex h-dvh flex-col overflow-hidden bg-surface"
            : "flex h-[calc(100dvh-9.5rem)] min-h-[32rem] flex-col overflow-hidden rounded-xl border border-line bg-surface"
        }
      >
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <LarisAvatar size={36} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">Laris · {embed ? embed.brand : "ImobiQ"}</p>
            <p className="truncate text-xs text-ink-2" aria-live="polite">
              {busy ? (activity ? `${activity}…` : "digitando…") : aiEnabled ? "online · responde na hora" : "deixe seu contato · um corretor retorna"}
            </p>
          </div>
          {telegram?.available && (
            <button
              type="button"
              onClick={continueOnTelegram}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-2 hover:bg-surface-2"
              title="Continuar esta conversa no Telegram"
              aria-label="Continuar no Telegram"
            >
              <Send aria-hidden size={13} /> Telegram
            </button>
          )}
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-2 hover:bg-surface-2"
            title={embed ? "Começar uma nova conversa" : "Começar uma nova conversa como outro lead"}
            aria-label="Nova conversa"
          >
            <RotateCcw aria-hidden size={13} /> {!embed && "Nova conversa"}
          </button>
          {embed && (
            <button
              type="button"
              onClick={() => embed.hostOrigin && window.parent.postMessage({ type: "imobiq:close" }, embed.hostOrigin)}
              className="grid size-8 place-items-center rounded-md text-ink-2 hover:bg-surface-2"
              aria-label="Fechar o chat"
            >
              <X aria-hidden size={18} />
            </button>
          )}
        </header>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-chat px-3 py-4 sm:px-6">
          <Bubble role="assistant" at={null}>
            <p>{welcome}</p>
          </Bubble>
          {messages.map((m) => (
            <div key={m.key} className="space-y-2">
              {(m.content || !m.streaming) && (
                <Bubble role={m.role} at={m.at}>
                  <Markdown>{m.content}</Markdown>
                </Bubble>
              )}
              {m.streaming && !m.content && <TypingBubble />}
              {!!m.properties?.length && (
                <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
                  {m.properties.map((p) => (
                    <PropertyCard key={p.id} property={p} />
                  ))}
                </div>
              )}
              {m.appointment && (
                <Notice icon={<CalendarCheck aria-hidden size={16} className="text-good" />}>
                  {m.appointment.tipo === "reuniao" ? "Reunião" : "Visita"} confirmada: {m.appointment.quando} com{" "}
                  {m.appointment.com}
                  {m.appointment.imovel ? ` · ${m.appointment.imovel}` : ""}
                </Notice>
              )}
              {m.handoff && (
                <Notice icon={<Headset aria-hidden size={16} className="text-brand" />}>
                  Encaminhado para {m.handoff.corretor}, retorno {m.handoff.prazo_retorno}
                </Notice>
              )}
            </div>
          ))}
          {askContact && <ContactForm onSubmit={sendContact} />}
          {aiEnabled && !messages.length && (
            <div className="flex flex-wrap gap-2 pt-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-ink hover:border-brand"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {error && <p className="border-t border-line bg-surface px-4 py-2 text-xs text-danger">{error}</p>}
        <form
          className="flex items-end gap-2 border-t border-line p-3"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            ref={inputRef}
            autoFocus={Boolean(embed?.draft)}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            maxLength={2000}
            placeholder="Escreva uma mensagem"
            aria-label="Mensagem"
            className="max-h-32 min-h-10 flex-1 resize-none rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-brand"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="grid size-10 place-items-center rounded-full bg-brand text-brand-ink disabled:opacity-40"
            aria-label="Enviar"
          >
            <SendHorizontal aria-hidden size={18} />
          </button>
        </form>
      </section>
  );

  if (embed) return chat;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
      {chat}
      <aside className="space-y-3 lg:h-[calc(100dvh-9.5rem)] lg:overflow-y-auto">
        <LeadPanel lead={lead} analysis={analysis} agent={agent} appointment={appointment} />
      </aside>
    </div>
  );
}

function Bubble({ role, at, children }: { role: UiMessage["role"]; at: string | null; children: React.ReactNode }) {
  const mine = role === "user";
  return (
    <div className={`flex items-end gap-2 ${mine ? "justify-end" : "justify-start"}`}>
      {!mine && <LarisAvatar size={26} />}
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed text-ink shadow-sm sm:max-w-[75%] ${
          mine ? "rounded-br-sm bg-bubble-user" : "rounded-bl-sm bg-bubble-agent"
        }`}
      >
        {role === "followup" && (
          <p className="mb-1 inline-flex items-center gap-1 text-[11px] font-medium text-brand">
            <BellRing aria-hidden size={11} /> follow-up automático
          </p>
        )}
        {children}
        {at && <p className="mt-1 text-right text-[10px] text-muted">{clockTime(at)}</p>}
      </div>
    </div>
  );
}

function ContactForm({ onSubmit }: { onSubmit: (name: string, phone: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(name.trim(), phone.trim());
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? "Confira o telefone: informe o DDD e o número."
          : "Não consegui enviar agora. Tente de novo em instantes.",
      );
    } finally {
      setBusy(false);
    }
  }

  const field =
    "w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-brand";
  return (
    <form onSubmit={submit} className="ml-8 max-w-sm space-y-2 rounded-2xl border border-line bg-surface p-3 shadow-sm">
      <p className="flex items-center gap-1.5 text-xs font-medium text-ink-2">
        <UserRound aria-hidden size={14} /> Seus dados para o corretor retornar
      </p>
      <label className="block">
        <span className="sr-only">Nome</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          minLength={2}
          maxLength={80}
          autoComplete="name"
          placeholder="Nome"
          className={field}
        />
      </label>
      <label className="block">
        <span className="sr-only">Telefone com DDD</span>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          required
          type="tel"
          inputMode="tel"
          maxLength={30}
          autoComplete="tel"
          placeholder="Telefone com DDD"
          className={field}
        />
      </label>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button
        type="submit"
        disabled={busy || name.trim().length < 2 || phone.trim().length < 8}
        className="w-full rounded-lg bg-brand px-3 py-2 text-sm font-medium text-brand-ink disabled:opacity-40"
      >
        {busy ? "Enviando…" : "Enviar contato"}
      </button>
    </form>
  );
}

function TypingBubble() {
  return (
    <div className="flex items-end justify-start gap-2">
      <LarisAvatar size={26} />
      <div className="typing flex gap-1 rounded-2xl rounded-bl-sm bg-bubble-agent px-4 py-3 shadow-sm" aria-label="Laris está digitando">
        <span className="size-1.5 rounded-full bg-muted" />
        <span className="size-1.5 rounded-full bg-muted" />
        <span className="size-1.5 rounded-full bg-muted" />
      </div>
    </div>
  );
}

function Notice({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex justify-center">
      <p className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink">
        {icon}
        {children}
      </p>
    </div>
  );
}
