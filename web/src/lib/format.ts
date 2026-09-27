export const brl = (value: number) =>
  value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

export const compactBrl = (value: number) =>
  value >= 1_000_000
    ? `R$ ${(value / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`
    : value >= 10_000
      ? `R$ ${Math.round(value / 1000).toLocaleString("pt-BR")} mil`
      : brl(value);

export const STATUS_ORDER = ["novo", "em_qualificacao", "qualificado", "agendado", "encaminhado", "perdido"] as const;

export const STATUS_LABEL: Record<string, string> = {
  novo: "Novo",
  em_qualificacao: "Em qualificação",
  qualificado: "Qualificado",
  agendado: "Agendado",
  encaminhado: "Encaminhado",
  perdido: "Perdido",
};

export const INTENT_LABEL: Record<string, string> = {
  compra: "Compra",
  aluguel: "Aluguel",
  investimento: "Investimento",
  indefinido: "Indefinido",
};

export const AGENT_LABEL: Record<string, string> = {
  compra_aluguel: "Especialista em locação e compra",
  investimento: "Especialista em investimentos",
  agendamento: "Agente de agendamento",
  follow_up: "Follow-up automático",
  pausa: "Recado automático (IA pausada)",
};

export const FIELD_LABEL: Record<string, string> = {
  intent: "Objetivo",
  name: "Nome",
  company: "Empresa",
  decision_maker: "Quem decide",
  business_activity: "Atividade",
  space: "Tamanho do espaço",
  regions: "Região",
  budget_max: "Faixa de preço",
  bedrooms: "Quartos",
  property_type: "Tipo de imóvel",
  urgency: "Urgência",
  financing: "Pagamento",
  investor_profile: "Perfil de investidor",
  ticket: "Ticket",
  expected_return: "Retorno esperado",
};

export const TOOL_ACTIVITY: Record<string, string> = {
  buscar_imoveis: "consultando imóveis",
  detalhes_imovel: "vendo os detalhes do imóvel",
  listar_horarios: "consultando a agenda",
  agendar: "confirmando o agendamento",
  transferir_para_humano: "chamando um corretor",
};

export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const future = diff < 0;
  const s = Math.abs(diff);
  const text =
    s < 60 ? "menos de 1 min" : s < 3600 ? `${Math.round(s / 60)} min` : s < 86400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`;
  return future ? `em ${text}` : `há ${text}`;
}

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });

export const clockTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });

export const DECISION_LABEL: Record<string, string> = {
  sim: "Decide sozinho(a)",
  compartilhada: "Decide com sócios/diretoria",
  nao: "Não decide (pesquisa para outra pessoa)",
};

/** Tamanho do espaço pedido: faixa de m² e/ou nº de pessoas. */
export function spaceLabel(lead: { area_min: number | null; area_max: number | null; headcount: number | null }) {
  const area =
    lead.area_min && lead.area_max
      ? `${lead.area_min}–${lead.area_max} m²`
      : lead.area_min
        ? `a partir de ${lead.area_min} m²`
        : lead.area_max
          ? `até ${lead.area_max} m²`
          : null;
  const people = lead.headcount ? `${lead.headcount} pessoas` : null;
  return [area, people].filter(Boolean).join(" · ") || null;
}

