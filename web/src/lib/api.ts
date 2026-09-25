const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
// No servidor (SSR dentro do Docker) a API é acessada pela rede interna do compose
export const API_URL =
  typeof window === "undefined" ? (process.env.INTERNAL_API_URL ?? PUBLIC_API_URL) : PUBLIC_API_URL;

export type Property = {
  id: string;
  title: string;
  property_type: string;
  purpose: "venda" | "aluguel";
  neighborhood: string;
  zone: string;
  city: string;
  price: number;
  condo_fee: number | null;
  iptu: number | null;
  bedrooms: number;
  suites: number;
  bathrooms: number;
  parking: number;
  area_m2: number;
  description: string;
  amenities: string[];
  furnished: boolean;
  pet_friendly: boolean;
  accepts_financing: boolean;
  estimated_yield: number | null;
  near_metro: boolean;
  available: boolean;
  similarity?: number | null;
};

export type Lead = {
  id: string;
  name: string | null;
  phone: string | null;
  email: string | null;
  channel: string;
  intent: string;
  property_type: string | null;
  budget_min: number | null;
  budget_max: number | null;
  bedrooms: number | null;
  regions: string[];
  urgency: string | null;
  timeline: string | null;
  financing: string | null;
  investor_profile: string | null;
  ticket: number | null;
  expected_return: string | null;
  extra: { preferences?: string; wants_meeting?: boolean; handoff_reason?: string };
  score: number;
  temperature: "quente" | "morno" | "frio";
  status: string;
  followup_count: number;
  last_message_at: string | null;
  next_followup_at: string | null;
  created_at: string;
};

export type ChatMessage = {
  id: number;
  role: "user" | "assistant" | "followup" | "system";
  content: string;
  agent: string | null;
  meta: {
    property_ids?: string[];
    attempt?: number;
    appointment?: { tipo: string; quando: string; com: string; imovel: string | null };
    handoff?: { corretor: string; prazo_retorno: string };
  };
  created_at: string;
};

export type Broker = { id: number; name: string; email: string; phone: string; role: string; zones: string[] };

export type Appointment = {
  id: string;
  lead_id: string;
  lead_name: string | null;
  kind: "visita" | "reuniao" | "videochamada";
  status: string;
  property_id: string | null;
  notes: string | null;
  start_at: string;
  broker: Broker;
};

export type BrokerSummary = {
  resumo: string;
  perfil: string;
  necessidades: string[];
  imoveis_de_interesse: string[];
  objecoes_e_duvidas: string[];
  proximos_passos: string[];
  abordagem_sugerida: string;
};

export type Summary = { id: number; content: BrokerSummary; text: string; created_at: string };

export type LeadDetail = Lead & {
  assigned_broker: Broker | null;
  summary: Summary | null;
  appointments: Appointment[];
  messages: ChatMessage[];
  missing: string[];
};

export type Metrics = {
  total_leads: number;
  leads_24h: number;
  by_status: Record<string, number>;
  by_temperature: Record<string, number>;
  by_intent: Record<string, number>;
  avg_score: number;
  qualification_rate: number;
  upcoming_appointments: number;
  followups_sent: number;
  awaiting_followup: number;
};

export type FollowupConfig = {
  enabled: boolean;
  minutes: number;
  max_attempts: number;
  quiet_hours: boolean;
  quiet_start: string;
  quiet_end: string;
};

export type DemoResetResult = { leads: number; appointments: number; slots: number };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} falhou: ${res.status}`);
  return res.json() as Promise<T>;
}

export const apiGet = <T,>(path: string) => request<T>(path);
export const apiPost = <T,>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export const apiPut = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// ---------------------------------------------------------------- streaming do chat (SSE)

export type ChatEvent =
  | { type: "analysis"; route: string; intent: string; score: number; temperature: Lead["temperature"]; status: string; missing: string[] }
  | { type: "agent"; agent: string }
  | { type: "token"; text: string }
  | { type: "tool"; name: string; status: "start" | "done" | "error"; input?: Record<string, unknown> }
  | { type: "properties"; items: Property[] }
  | { type: "appointment"; id: string; tipo: string; quando: string; com: string; imovel: string | null }
  | { type: "handoff"; corretor: string; prazo_retorno: string }
  | { type: "error"; message: string }
  | { type: "done"; reply: string; agent: string | null; lead: Lead };

/** Envia a mensagem e entrega cada evento SSE da resposta (fetch + ReadableStream, pois é POST). */
export async function streamChat(leadId: string, content: string, onEvent: (event: ChatEvent) => void) {
  const res = await fetch(`${API_URL}/chat/${leadId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok || !res.body) throw new Error(`Falha ao enviar mensagem: ${res.status}`);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (data) onEvent(JSON.parse(data) as ChatEvent);
    }
  }
}
