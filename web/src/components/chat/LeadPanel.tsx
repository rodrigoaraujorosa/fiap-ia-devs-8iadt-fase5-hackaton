import { Bot, CalendarCheck, CircleDashed, CircleCheck } from "lucide-react";

import { Card, ScoreMeter, StatusBadge, TemperatureBadge } from "@/components/ui";
import type { Lead } from "@/lib/api";
import { AGENT_LABEL, FIELD_LABEL, INTENT_LABEL, compactBrl } from "@/lib/format";

export type Analysis = { route: string; missing: string[] };
export type AppointmentInfo = { tipo: string; quando: string; com: string; imovel: string | null };

function profileRows(lead: Lead): [string, string][] {
  const money = (v: number | null) => (v ? compactBrl(v) : null);
  const rows: [string, string | null][] = [
    ["Nome", lead.name],
    ["Telefone", lead.phone ?? (lead.extra?.phone_declined ? "preferiu não informar" : null)],
    ["Objetivo", INTENT_LABEL[lead.intent] ?? lead.intent],
    ["Tipo", lead.property_type],
    ["Região", lead.regions.length ? lead.regions.join(", ") : null],
    ["Orçamento", lead.budget_max ? `até ${money(lead.budget_max)}${lead.intent === "aluguel" ? "/mês" : ""}` : null],
    ["Quartos", lead.bedrooms ? `${lead.bedrooms}+` : null],
    ["Urgência", lead.urgency ? `${lead.urgency}${lead.timeline ? ` (${lead.timeline})` : ""}` : null],
    ["Pagamento", lead.financing],
    ["Perfil investidor", lead.investor_profile],
    ["Ticket", money(lead.ticket)],
    ["Retorno esperado", lead.expected_return],
    ["Preferências", lead.extra?.preferences ?? null],
  ];
  return rows.filter((r): r is [string, string] => Boolean(r[1]) && r[1] !== "Indefinido");
}

export function LeadPanel({ lead, analysis, agent, appointment }: {
  lead: Lead | null;
  analysis: Analysis | null;
  agent: string | null;
  appointment: AppointmentInfo | null;
}) {
  if (!lead) {
    return (
      <Card title="O que a IA está entendendo">
        <p className="text-sm text-ink-2">
          Assim que o lead escrever, este painel mostra em tempo real o que o supervisor extraiu da conversa: objetivo,
          orçamento, região, urgência, score e o que ainda falta descobrir.
        </p>
      </Card>
    );
  }
  const rows = profileRows(lead);
  const missing = analysis?.missing ?? [];

  return (
    <div className="space-y-3">
      <Card title="O que a IA está entendendo">
        <div className="flex flex-wrap items-center gap-2">
          <TemperatureBadge value={lead.temperature} />
          <StatusBadge value={lead.status} />
        </div>
        <div className="mt-3">
          <p className="mb-1 text-xs text-ink-2">Score de qualificação</p>
          <ScoreMeter score={lead.score} />
        </div>
        {agent && (
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-ink-2">
            <Bot aria-hidden size={14} className="text-brand" />
            Respondendo: <strong className="font-medium text-ink">{AGENT_LABEL[agent] ?? agent}</strong>
          </p>
        )}
      </Card>

      {appointment && (
        <Card title="Agendamento">
          <p className="flex items-start gap-2 text-sm text-ink">
            <CalendarCheck aria-hidden size={16} className="mt-0.5 shrink-0 text-good" />
            <span>
              {appointment.tipo === "reuniao" ? "Reunião" : "Visita"} {appointment.quando} com {appointment.com}
              {appointment.imovel ? ` · ${appointment.imovel}` : ""}
            </span>
          </p>
        </Card>
      )}

      <Card title="Perfil extraído">
        {rows.length ? (
          <dl className="space-y-1.5 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="grid grid-cols-[7rem_1fr] gap-2">
                <dt className="text-ink-2">{label}</dt>
                <dd className="text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-muted">Nada extraído ainda.</p>
        )}
      </Card>

      <Card title="Próximas perguntas da qualificação">
        {missing.length ? (
          <ul className="space-y-1 text-sm">
            {missing.map((field, i) => (
              <li key={field} className="flex items-center gap-2 text-ink-2">
                <CircleDashed aria-hidden size={14} className={i === 0 ? "text-brand" : "text-muted"} />
                {FIELD_LABEL[field] ?? field}
                {i === 0 && <span className="text-xs text-muted">(prioridade)</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 text-sm text-ink">
            <CircleCheck aria-hidden size={14} className="text-good" /> Qualificação completa
          </p>
        )}
      </Card>
    </div>
  );
}
