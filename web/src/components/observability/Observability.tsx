"use client";

import { ExternalLink, RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminGate } from "@/components/AdminGate";
import { BarList } from "@/components/BarList";
import { Card, EmptyState, StatTile } from "@/components/ui";
import { ApiError, apiGet, type Insights, type InsightsPeriod } from "@/lib/api";

const PERIODS: { key: InsightsPeriod; label: string }[] = [
  { key: "24h", label: "24 horas" },
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
];

// nomes das observações no Langfuse → nome no painel
const AGENT_LABEL: Record<string, string> = {
  extrair_perfil: "Supervisor (Haiku)",
  "compra_aluguel.llm": "Locação e compra",
  "investimento.llm": "Investimentos",
  "agendamento.llm": "Agendamento",
  gerar_follow_up: "Follow-up",
  resumo_corretor: "Resumo ao corretor",
};
const TOOL_LABEL: Record<string, string> = {
  buscar_imoveis: "Busca de imóveis",
  detalhes_imovel: "Detalhes do imóvel",
  listar_horarios: "Consulta à agenda",
  agendar: "Agendamento",
  transferir_para_humano: "Encaminhamento",
};
const MODEL_LABEL: Record<string, string> = { "claude-sonnet-5": "Claude Sonnet 5", "claude-haiku-4-5": "Claude Haiku 4.5" };

function usd(value: number): string {
  const digits = value > 0 && value < 0.1 ? 3 : 2;
  return `US$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function brl(value: number, rate: number): string {
  return `≈ ${(value * rate).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}`;
}

function seconds(ms: number): string {
  return `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
}

function percent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

/** Custo por dia (ou por hora, em 24h): barras verticais de série única, com tooltip por barra. */
function DailyBars({ data, hourly }: { data: Insights["daily"]; hourly: boolean }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.cost), 0);
  if (!data.length || max === 0) return <EmptyState>Sem custo com IA neste período.</EmptyState>;

  const label = (iso: string) => {
    const date = new Date(hourly ? iso : `${iso.slice(0, 10)}T12:00:00`);
    return hourly
      ? date.toLocaleTimeString("pt-BR", { hour: "2-digit" }).replace(":00", "") + "h"
      : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  };
  const every = Math.ceil(data.length / 8); // no máximo ~8 rótulos no eixo, para não encavalar
  return (
    <div>
      <div className="relative flex h-40 items-end gap-0.5 border-b border-line" role="list" aria-label="Custo por período">
        {data.map((d, i) => (
          <button
            key={d.date}
            type="button"
            role="listitem"
            className="group relative flex h-full flex-1 items-end outline-none focus-visible:ring-2 focus-visible:ring-data"
            onPointerEnter={() => setActive(i)}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
            aria-label={`${label(d.date)}: ${usd(d.cost)}`}
          >
            <span
              className={`w-full rounded-t-[4px] bg-data transition-opacity ${active !== null && active !== i ? "opacity-50" : ""}`}
              style={{ height: d.cost ? `max(2px, ${(d.cost / max) * 100}%)` : 0 }}
            />
            {active === i && (
              <span
                role="tooltip"
                className={`pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-md border border-line bg-surface px-2 py-1 text-xs shadow-md ${
                  i > data.length / 2 ? "right-0" : "left-0"
                }`}
              >
                <strong className="tabular font-semibold text-ink">{usd(d.cost)}</strong>{" "}
                <span className="text-ink-2">· {label(d.date)}</span>
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="mt-1 flex gap-0.5 text-[10px] text-muted" aria-hidden>
        {data.map((d, i) => (
          <span key={d.date} className="flex-1 text-center">
            {i % every === 0 ? label(d.date) : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function Dashboard({ data }: { data: Insights }) {
  const t = data.totals;
  const rate = data.usd_brl;
  const perUnit = (value: number | null) => (value === null ? "—" : usd(value));
  const agents = data.by_agent.map((a) => ({ key: a.name, label: AGENT_LABEL[a.name] ?? a.name, value: a.cost }));
  const models = data.by_model.map((m) => ({ key: m.model, label: MODEL_LABEL[m.model] ?? m.model, value: m.cost }));
  const tools = data.tools.map((x) => ({ key: x.name, label: TOOL_LABEL[x.name] ?? x.name, value: x.calls }));

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label="Custo com IA" value={usd(t.cost)} hint={`${brl(t.cost, rate)} · ${t.llm_calls} chamadas ao Claude`} />
        <StatTile
          label="Custo por conversa"
          value={perUnit(t.cost_per_conversation)}
          hint={`${t.conversations} conversas no período`}
        />
        <StatTile
          label="Custo por visita agendada"
          value={perUnit(t.cost_per_appointment)}
          hint={
            t.cost_per_appointment === null
              ? "nenhuma visita no período"
              : `${brl(t.cost_per_appointment, rate)} · ${t.appointments} visitas`
          }
        />
        <StatTile
          label="Economia com cache"
          value={usd(data.cache.savings)}
          hint={`${percent(data.cache.hit_rate)} dos tokens de entrada vieram do cache`}
        />
        <StatTile
          label="Tempo de resposta"
          value={data.latency.p50_ms ? seconds(data.latency.p50_ms) : "—"}
          hint={data.latency.p95_ms ? `mediana · 95% em até ${seconds(data.latency.p95_ms)}` : "sem turnos no período"}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title={data.period === "24h" ? "Custo por hora" : "Custo por dia"}>
            <DailyBars data={data.daily} hourly={data.period === "24h"} />
          </Card>
        </div>
        <Card title="Custo por modelo">
          {models.length ? <BarList rows={models} unit="" format={usd} /> : <EmptyState>Sem chamadas.</EmptyState>}
          <p className="mt-3 text-xs text-muted">
            O Haiku, mais barato, lê cada mensagem e extrai o perfil do lead; o Sonnet conversa e usa as ferramentas.
          </p>
        </Card>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card title="Custo por agente">
          {agents.length ? <BarList rows={agents} unit="" format={usd} /> : <EmptyState>Sem chamadas.</EmptyState>}
        </Card>
        <Card title="Ferramentas usadas pelos agentes">
          {tools.length ? <BarList rows={tools} unit="chamadas" /> : <EmptyState>Nenhuma ferramenta usada.</EmptyState>}
        </Card>
        <Card title="Segurança e volume">
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <dt className="flex items-center gap-1.5 text-ink-2">
                <ShieldAlert aria-hidden size={15} className={data.injections ? "text-warm" : "text-muted"} />
                Tentativas de prompt injection
              </dt>
              <dd className="tabular font-semibold text-ink">{data.injections}</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-ink-2">Mensagens respondidas pela IA</dt>
              <dd className="tabular font-semibold text-ink">{t.turns}</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-ink-2">Custo por lead qualificado</dt>
              <dd className="tabular font-semibold text-ink">{perUnit(t.cost_per_qualified)}</dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-ink-2">Tokens (entrada · saída)</dt>
              <dd className="tabular font-semibold text-ink">
                {(data.tokens.input + data.tokens.cache_read + data.tokens.cache_creation).toLocaleString("pt-BR")} ·{" "}
                {data.tokens.output.toLocaleString("pt-BR")}
              </dd>
            </div>
          </dl>
          {data.links.project_url && (
            <a
              href={data.links.project_url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand underline-offset-2 hover:underline"
            >
              Ver os traces no Langfuse <ExternalLink aria-hidden size={13} />
            </a>
          )}
        </Card>
      </div>

      <p className="text-xs text-muted">
        Fonte: Langfuse (ambiente <code>{data.environment}</code>) e banco do ImobiQ · atualizado{" "}
        {new Date(data.generated_at).toLocaleTimeString("pt-BR")} (os dados do Langfuse podem ter alguns minutos de
        atraso) · custos em dólar, convertidos a R$ {rate.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}.
      </p>
    </div>
  );
}

function Content() {
  const [period, setPeriod] = useState<InsightsPeriod>("7d");
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (p: InsightsPeriod) => {
    setLoading(true);
    setError(null);
    try {
      setData(await apiGet<Insights>(`/observability?period=${p}`));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 502 ? err.message : "Não consegui carregar os dados.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(() => load(period), 0);
    const timer = window.setInterval(() => load(period), 60_000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load, period]);

  return (
    <div className={`space-y-4 transition-opacity ${loading && data ? "opacity-70" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <div role="radiogroup" aria-label="Período" className="inline-flex rounded-lg border border-line bg-surface p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              type="button"
              role="radio"
              aria-checked={period === p.key}
              onClick={() => setPeriod(p.key)}
              className={`rounded-md px-3 py-1 text-sm ${period === p.key ? "bg-brand text-white" : "text-ink-2 hover:text-ink"}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => load(period)}
          className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs text-ink-2 hover:text-ink"
        >
          <RefreshCw aria-hidden size={13} className={loading ? "animate-spin" : ""} /> Atualizar
        </button>
        {data?.links.project_url && (
          <a
            href={data.links.project_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink hover:border-brand"
          >
            Abrir o Langfuse <ExternalLink aria-hidden size={14} />
          </a>
        )}
      </div>
      {error && <p className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-danger">{error}</p>}
      {!data && !error && <div className="h-64 animate-pulse rounded-xl bg-surface-2" />}
      {data && !data.enabled && (
        <Card title="Langfuse não configurado">
          <p className="text-sm text-ink-2">
            Coloque <code>LANGFUSE_PUBLIC_KEY</code> e <code>LANGFUSE_SECRET_KEY</code> no <code>.env</code> e reinicie a API:
            cada conversa passa a gerar traces com custo, tokens e latência, e este painel resume tudo.
          </p>
        </Card>
      )}
      {data?.enabled && <Dashboard data={data} />}
    </div>
  );
}

export function Observability() {
  return (
    <AdminGate
      title="Observabilidade"
      subtitle="Custo com IA, uso dos agentes e desempenho, em resumo. O detalhe de cada chamada fica no Langfuse."
      className="space-y-4"
    >
      <Content />
    </AdminGate>
  );
}
