"use client";

import { ArrowLeft, BellRing, CalendarCheck, Loader2, Sparkles, UserRound } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card, EmptyState, Markdown, ScoreMeter, StatusBadge, Tag, TemperatureBadge } from "@/components/ui";
import { apiGet, apiPost, type LeadDetail, type Summary } from "@/lib/api";
import { AGENT_LABEL, FIELD_LABEL, INTENT_LABEL, compactBrl, dateTime, relativeTime } from "@/lib/format";

function SummaryBlock({ summary }: { summary: Summary }) {
  const s = summary.content;
  const list = (items: string[]) =>
    items.length ? (
      <ul className="list-disc space-y-0.5 pl-4 text-sm text-ink">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-muted">Nenhum.</p>
    );
  return (
    <div className="space-y-3">
      <p className="text-sm leading-relaxed text-ink">{s.resumo}</p>
      <p className="text-sm text-ink-2">
        <strong className="font-medium text-ink">Perfil:</strong> {s.perfil}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink-2">Necessidades</h3>
          {list(s.necessidades)}
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink-2">Próximos passos</h3>
          {list(s.proximos_passos)}
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink-2">Objeções e dúvidas</h3>
          {list(s.objecoes_e_duvidas)}
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink-2">Imóveis de interesse</h3>
          <div className="flex flex-wrap gap-1">
            {s.imoveis_de_interesse.length ? s.imoveis_de_interesse.map((id) => <Tag key={id}>{id}</Tag>) : <span className="text-sm text-muted">Nenhum.</span>}
          </div>
        </div>
      </div>
      <p className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-ink">
        <strong className="font-medium">Abordagem sugerida:</strong> {s.abordagem_sugerida}
      </p>
      <p className="text-xs text-muted">Gerado {relativeTime(summary.created_at)}</p>
    </div>
  );
}

export function LeadDetailView({ id }: { id: string }) {
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      setLead(await apiGet<LeadDetail>(`/leads/${id}`));
    } catch {
      setError("Lead não encontrado ou API fora do ar.");
    }
  }, [id]);

  useEffect(() => {
    const first = window.setTimeout(load, 0); // 1ª carga fora do corpo síncrono do efeito
    const timer = window.setInterval(load, 10_000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load]);

  async function generateSummary() {
    setGenerating(true);
    try {
      const summary = await apiPost<Summary>(`/leads/${id}/summary`);
      setLead((l) => (l ? { ...l, summary } : l));
    } catch {
      setError("Não foi possível gerar o resumo agora.");
    } finally {
      setGenerating(false);
    }
  }

  if (!lead) return <EmptyState>{error ?? "Carregando…"}</EmptyState>;

  const profile: [string, string | null][] = [
    ["Objetivo", INTENT_LABEL[lead.intent] ?? lead.intent],
    ["Tipo", lead.property_type],
    ["Região", lead.regions.join(", ") || null],
    ["Orçamento", lead.budget_max ? `até ${compactBrl(lead.budget_max)}${lead.intent === "aluguel" ? "/mês" : ""}` : null],
    ["Quartos", lead.bedrooms ? `${lead.bedrooms}+` : null],
    ["Urgência", lead.urgency ? `${lead.urgency}${lead.timeline ? ` (${lead.timeline})` : ""}` : null],
    ["Pagamento", lead.financing],
    ["Perfil investidor", lead.investor_profile],
    ["Ticket", lead.ticket ? compactBrl(lead.ticket) : null],
    ["Retorno esperado", lead.expected_return],
    ["Preferências", lead.extra?.preferences ?? null],
    ["Motivo do encaminhamento", lead.extra?.handoff_reason ?? null],
  ];

  return (
    <div className="space-y-4">
      <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft aria-hidden size={14} /> Voltar ao dashboard
      </Link>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-ink">{lead.name ?? "Lead sem nome"}</h1>
        <TemperatureBadge value={lead.temperature} />
        <StatusBadge value={lead.status} />
        <div className="w-40">
          <ScoreMeter score={lead.score} />
        </div>
      </div>
      <p className="text-sm text-ink-2">
        Canal {lead.channel} · criado {relativeTime(lead.created_at)} · último contato {relativeTime(lead.last_message_at)}
        {lead.assigned_broker && (
          <>
            {" "}
            · <UserRound aria-hidden size={13} className="inline" /> {lead.assigned_broker.name}
          </>
        )}
      </p>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card
            title="Resumo para o corretor"
            action={
              <button
                type="button"
                onClick={generateSummary}
                disabled={generating}
                className="inline-flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-brand-ink disabled:opacity-60"
              >
                {generating ? <Loader2 aria-hidden size={13} className="animate-spin" /> : <Sparkles aria-hidden size={13} />}
                {lead.summary ? "Atualizar resumo" : "Gerar resumo"}
              </button>
            }
          >
            {lead.summary ? (
              <SummaryBlock summary={lead.summary} />
            ) : (
              <EmptyState>O resumo é gerado automaticamente ao agendar ou encaminhar, ou sob demanda.</EmptyState>
            )}
          </Card>

          <Card title="Perfil do lead">
            <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
              {profile
                .filter(([, v]) => v && v !== "Indefinido")
                .map(([label, value]) => (
                  <div key={label} className="grid grid-cols-[7.5rem_1fr] gap-2 sm:col-span-2">
                    <dt className="text-ink-2">{label}</dt>
                    <dd className="text-ink">{value}</dd>
                  </div>
                ))}
            </dl>
            {!!lead.missing.length && (
              <p className="mt-3 text-xs text-muted">
                Ainda falta: {lead.missing.map((f) => FIELD_LABEL[f] ?? f).join(", ")}
              </p>
            )}
          </Card>

          <Card title="Agendamentos">
            {lead.appointments.length ? (
              <ul className="space-y-2">
                {lead.appointments.map((a) => (
                  <li key={a.id} className="flex items-start gap-2 text-sm">
                    <CalendarCheck aria-hidden size={15} className={`mt-0.5 ${a.status === "cancelado" ? "text-muted" : "text-good"}`} />
                    <span className={a.status === "cancelado" ? "text-muted line-through" : "text-ink"}>
                      {a.kind === "reuniao" ? "Reunião" : "Visita"} {dateTime(a.start_at)} com {a.broker.name}
                      {a.property_id ? ` · ${a.property_id}` : ""}
                      {a.status === "cancelado" ? " (remarcado)" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState>Sem agendamentos.</EmptyState>
            )}
          </Card>
        </div>

        <Card title={`Conversa (${lead.messages.length} mensagens)`}>
          <ol className="max-h-[70vh] space-y-2 overflow-y-auto rounded-lg bg-chat p-3">
            {lead.messages.map((m) => {
              const mine = m.role === "user";
              return (
                <li key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm text-ink shadow-sm ${
                      mine ? "rounded-br-sm bg-bubble-user" : "rounded-bl-sm bg-bubble-agent"
                    }`}
                  >
                    {m.role === "followup" && (
                      <p className="mb-1 inline-flex items-center gap-1 text-[11px] font-medium text-brand">
                        <BellRing aria-hidden size={11} /> follow-up automático #{m.meta?.attempt}
                      </p>
                    )}
                    {m.role === "assistant" && m.agent && (
                      <p className="mb-1 text-[11px] text-muted">{AGENT_LABEL[m.agent] ?? m.agent}</p>
                    )}
                    <Markdown>{m.content}</Markdown>
                    <p className="mt-1 text-right text-[10px] text-muted">{dateTime(m.created_at)}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>
      </div>
    </div>
  );
}
