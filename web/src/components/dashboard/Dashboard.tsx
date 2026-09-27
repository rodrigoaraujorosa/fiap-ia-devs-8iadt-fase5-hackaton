"use client";

import { BellRing, CalendarDays, PauseCircle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { BarList } from "@/components/BarList";
import { Card, EmptyState, ScoreMeter, StatTile, StatusBadge, TemperatureBadge } from "@/components/ui";
import { apiGet, type Appointment, type Lead, type Metrics } from "@/lib/api";
import { INTENT_LABEL, STATUS_LABEL, STATUS_ORDER, compactBrl, dateTime, relativeTime, spaceLabel } from "@/lib/format";

const REFRESH_MS = 10_000;
const CHANNEL_TAG: Record<string, string> = { telegram: "via Telegram", site: "via site" };
const FILTERS = {
  status: { label: "Etapa", options: STATUS_ORDER.map((s) => [s, STATUS_LABEL[s]] as const) },
  temperature: { label: "Temperatura", options: [["quente", "Quente"], ["morno", "Morno"], ["frio", "Frio"]] as const },
  intent: { label: "Intenção", options: Object.entries(INTENT_LABEL) },
} as const;
type FilterKey = keyof typeof FILTERS;

function need(lead: Lead): string {
  if (lead.intent === "investimento") return lead.ticket ? `ticket ${compactBrl(lead.ticket)}` : "investidor";
  const parts = [
    lead.business_activity ?? lead.property_type,
    spaceLabel(lead),
    lead.bedrooms ? `${lead.bedrooms}+ qtos` : null,
    lead.regions[0],
    lead.budget_max ? `até ${compactBrl(lead.budget_max)}` : null,
  ].filter(Boolean);
  return parts.join(" · ") || "—";
}

export function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [filters, setFilters] = useState<Record<FilterKey, string>>({ status: "", temperature: "", intent: "" });
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    try {
      const [m, l, a] = await Promise.all([
        apiGet<Metrics>("/dashboard/metrics"),
        apiGet<Lead[]>(`/leads${query ? `?${query}` : ""}`),
        apiGet<Appointment[]>("/appointments"),
      ]);
      setMetrics(m);
      setLeads(l);
      setAppointments(a);
      setUpdatedAt(new Date());
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const first = window.setTimeout(load, 0); // 1ª carga fora do corpo síncrono do efeito
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load]);

  const hot = metrics?.by_temperature.quente ?? 0;
  const funnel = STATUS_ORDER.map((s) => ({ key: s, label: STATUS_LABEL[s], value: metrics?.by_status[s] ?? 0 }));
  const intents = Object.entries(INTENT_LABEL).map(([k, label]) => ({ key: k, label, value: metrics?.by_intent[k] ?? 0 }));

  return (
    <div className={`space-y-4 transition-opacity ${loading && metrics ? "opacity-80" : ""}`}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Dashboard do corretor</h1>
          <p className="text-sm text-ink-2">Leads atendidos pela Laris, qualificação e próximos passos.</p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs text-ink-2 hover:text-ink"
        >
          <RefreshCw aria-hidden size={13} className={loading ? "animate-spin" : ""} />
          {updatedAt ? `Atualizado ${updatedAt.toLocaleTimeString("pt-BR")}` : "Carregando"}
        </button>
      </div>

      {metrics && !metrics.ai_enabled && (
        <p role="status" className="flex flex-wrap items-center gap-1.5 rounded-lg border border-warm/40 bg-warm/10 px-3 py-2 text-sm text-ink">
          <PauseCircle aria-hidden size={16} className="shrink-0 text-warm" />
          <strong className="font-medium">Atendimento com IA pausado.</strong>
          O chat e o Telegram respondem um recado fixo e guardam a mensagem; follow-ups e resumos estão parados.
          <Link href="/configuration" className="font-medium text-brand underline-offset-2 hover:underline">
            Religar
          </Link>
        </p>
      )}

      {failed && (
        <p className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-danger">
          Não foi possível carregar os dados. Verifique se a API está no ar.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Leads atendidos" value={metrics?.total_leads ?? "—"} hint={metrics ? `${metrics.leads_24h} nas últimas 24h` : undefined} />
        <StatTile
          label="Taxa de qualificação"
          value={metrics ? `${Math.round(metrics.qualification_rate * 100)}%` : "—"}
          hint="qualificados, agendados ou encaminhados"
        />
        <StatTile label="Leads quentes" value={metrics ? hot : "—"} hint={metrics ? `score médio ${metrics.avg_score}` : undefined} />
        <StatTile label="Agendamentos futuros" value={metrics?.upcoming_appointments ?? "—"} hint="visitas e reuniões" />
        <StatTile
          label="Follow-ups enviados"
          value={metrics?.followups_sent ?? "—"}
          hint={metrics ? `${metrics.awaiting_followup} leads aguardando` : undefined}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card title="Funil de atendimento">
          <BarList rows={funnel} total={metrics?.total_leads} />
        </Card>
        <Card title="Intenção dos leads">
          <BarList rows={intents} total={metrics?.total_leads} />
        </Card>
        <Card
          title="Próximos agendamentos"
          action={<CalendarDays aria-hidden size={15} className="text-muted" />}
        >
          {appointments.length ? (
            <ul className="max-h-56 space-y-2 overflow-y-auto pr-1">
              {appointments.map((a) => (
                <li key={a.id}>
                  <Link href={`/dashboard/leads/${a.lead_id}`} className="block rounded-md px-2 py-1.5 hover:bg-surface-2">
                    <p className="text-sm font-medium text-ink">
                      {a.lead_name ?? "Lead sem nome"} · {a.kind === "reuniao" ? "Reunião" : "Visita"}
                    </p>
                    <p className="text-xs text-ink-2">
                      {dateTime(a.start_at)} · {a.broker.name}
                      {a.property_id ? ` · ${a.property_id}` : ""}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Nenhum agendamento futuro.</EmptyState>
          )}
        </Card>
      </div>

      <Card
        title={`Leads (${leads.length})`}
        action={
          <div className="flex flex-wrap gap-2">
            {(Object.keys(FILTERS) as FilterKey[]).map((key) => (
              <label key={key} className="text-xs text-ink-2">
                <span className="sr-only">{FILTERS[key].label}</span>
                <select
                  value={filters[key]}
                  onChange={(e) => setFilters((f) => ({ ...f, [key]: e.target.value }))}
                  className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink"
                >
                  <option value="">{FILTERS[key].label}: todas</option>
                  {FILTERS[key].options.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        }
      >
        {leads.length ? (
          <div className="-mx-4 overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="px-4 py-2 font-medium">Lead</th>
                  <th className="px-2 py-2 font-medium">Intenção</th>
                  <th className="px-2 py-2 font-medium">Procura</th>
                  <th className="px-2 py-2 font-medium">Score</th>
                  <th className="px-2 py-2 font-medium">Temperatura</th>
                  <th className="px-2 py-2 font-medium">Etapa</th>
                  <th className="px-4 py-2 font-medium">Último contato</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-b border-line last:border-0 hover:bg-surface-2">
                    <td className="px-4 py-2">
                      <Link href={`/dashboard/leads/${lead.id}`} className="font-medium text-ink hover:text-brand">
                        {lead.name ?? "Sem nome"}
                      </Link>
                      {(lead.company || lead.channel !== "web") && (
                        <p className="text-xs text-ink-2">
                          {[lead.company, CHANNEL_TAG[lead.channel]].filter(Boolean).join(" · ")}
                        </p>
                      )}
                      {lead.next_followup_at && (
                        <p className="flex items-center gap-1 text-[11px] text-muted">
                          <BellRing aria-hidden size={10} /> follow-up {relativeTime(lead.next_followup_at)}
                        </p>
                      )}
                    </td>
                    <td className="px-2 py-2 text-ink-2">{INTENT_LABEL[lead.intent] ?? lead.intent}</td>
                    <td className="max-w-56 truncate px-2 py-2 text-ink-2" title={need(lead)}>
                      {need(lead)}
                    </td>
                    <td className="px-2 py-2">
                      <ScoreMeter score={lead.score} compact />
                    </td>
                    <td className="px-2 py-2">
                      <TemperatureBadge value={lead.temperature} />
                    </td>
                    <td className="px-2 py-2">
                      <StatusBadge value={lead.status} />
                    </td>
                    <td className="tabular px-4 py-2 text-xs text-ink-2">{relativeTime(lead.last_message_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>{metrics ? "Nenhum lead com esses filtros." : "Carregando leads…"}</EmptyState>
        )}
      </Card>
    </div>
  );
}
