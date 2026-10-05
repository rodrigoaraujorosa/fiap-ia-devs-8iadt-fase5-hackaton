import { BellRing, CalendarCheck, ExternalLink, FileText, MessagesSquare, SearchCheck, Target } from "lucide-react";
import Link from "next/link";

import { LogoMark } from "@/components/Brand";
import { apiGet } from "@/lib/api";

async function apiOnline() {
  try {
    return (await apiGet<{ status: string }>("/health")).status === "ok";
  } catch {
    return false;
  }
}

/** Site fictício da imobiliária, com o widget da Laris (o endereço vem da API: muda entre local e produção). */
async function siteUrl() {
  try {
    return (await apiGet<{ site_url: string }>("/info")).site_url;
  } catch {
    return null;
  }
}

const FEATURES = [
  { icon: MessagesSquare, title: "Atendimento na hora", text: "Conversa humanizada, 24/7, uma pergunta por vez." },
  {
    icon: Target,
    title: "Qualificação B2B",
    text: "Entende a empresa, a atividade, o espaço, o orçamento, quem decide e o prazo, e calcula um score.",
  },
  { icon: SearchCheck, title: "Imóveis certos", text: "Busca híbrida (semântica + texto) na base da imobiliária." },
  { icon: CalendarCheck, title: "Agendamento", text: "Marca visitas e reuniões com o corretor especialista no tipo de imóvel." },
  {
    icon: FileText,
    title: "Resumo para o corretor",
    text: "Briefing com perfil, objeções e próximos passos, enviado por e-mail com o convite da visita para a agenda.",
  },
  { icon: BellRing, title: "Follow-up automático", text: "Retoma leads que sumiram, com o contexto da conversa." },
];

export default async function Home() {
  const [online, site] = await Promise.all([apiOnline(), siteUrl()]);

  return (
    <div className="space-y-10 py-4">
      <section className="max-w-3xl space-y-4">
        <LogoMark size={56} />
        <p className="text-sm font-medium text-brand">Hackathon FIAP · Pós Tech IA para Devs · Turma 8IADT · Grupo 65</p>
        <h1 className="text-4xl font-semibold leading-tight text-ink">
          Nenhum lead sem resposta. Todo corretor com o cliente certo.
        </h1>
        <p className="text-lg text-ink-2">
          A Laris é uma SDR com IA generativa para imóveis comerciais: atende empresas e investidores na hora,
          qualifica, mostra conjuntos, andares corporativos, prédios e galpões, agenda visitas e envia ao corretor,
          por e-mail, um resumo pronto com o convite da visita.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/chat" className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-ink">
            Conversar como lead
          </Link>
          <Link href="/dashboard" className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-ink">
            Abrir dashboard do corretor
          </Link>
          {site && (
            <a
              href={site}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-ink"
            >
              Ver o site da imobiliária de exemplo <ExternalLink aria-hidden size={14} />
            </a>
          )}
        </div>
        {site && (
          <p className="text-sm text-ink-2">
            O site de exemplo mostra a Laris embutida no site de uma imobiliária fictícia: a bolha do chat aparece em
            todas as páginas e ela já sabe qual imóvel o visitante está vendo.
          </p>
        )}
        <p className="inline-flex items-center gap-2 text-xs text-ink-2">
          <span className={`size-2 rounded-full ${online ? "bg-good" : "bg-danger"}`} aria-hidden />
          API {online ? "online" : "offline"}
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <article key={title} className="rounded-xl border border-line bg-surface p-4">
            <Icon aria-hidden size={18} className="text-brand" />
            <h2 className="mt-2 text-sm font-semibold text-ink">{title}</h2>
            <p className="mt-1 text-sm text-ink-2">{text}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
