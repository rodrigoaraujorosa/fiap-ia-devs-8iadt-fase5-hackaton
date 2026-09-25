import { Flame, Snowflake, Thermometer } from "lucide-react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";

import type { Lead } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";

export function Card({ title, action, children, className = "" }: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-4 ${className}`}>
      {(title || action) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

const TEMPERATURE = {
  quente: { label: "Quente", icon: Flame, className: "text-hot" },
  morno: { label: "Morno", icon: Thermometer, className: "text-warm" },
  frio: { label: "Frio", icon: Snowflake, className: "text-cold" },
} as const;

export function TemperatureBadge({ value }: { value: Lead["temperature"] }) {
  const t = TEMPERATURE[value] ?? TEMPERATURE.frio;
  const Icon = t.icon;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink">
      <Icon aria-hidden size={13} className={t.className} />
      {t.label}
    </span>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const tone =
    value === "agendado" || value === "encaminhado"
      ? "bg-brand-soft text-ink"
      : value === "perdido"
        ? "bg-surface-2 text-muted line-through decoration-muted/40"
        : "bg-surface-2 text-ink-2";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>{STATUS_LABEL[value] ?? value}</span>;
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="inline-block rounded-md bg-surface-2 px-2 py-0.5 text-xs text-ink-2">{children}</span>;
}

/** Medidor de score: preenchimento na cor de dados, trilho num tom mais claro da mesma rampa. */
export function ScoreMeter({ score, compact = false }: { score: number; compact?: boolean }) {
  return (
    <div className="flex items-center gap-2" title={`Score ${score}/100`}>
      <div className={`h-1.5 overflow-hidden rounded-full bg-data-track ${compact ? "w-16" : "w-full"}`}>
        <div className="h-full rounded-full bg-data transition-all duration-500" style={{ width: `${score}%` }} />
      </div>
      <span className="tabular text-xs font-medium text-ink-2">{score}</span>
    </div>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-xs text-ink-2">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Normaliza o estilo "WhatsApp" do modelo: marcadores "•" viram lista e quebras simples de linha são mantidas. */
function normalizeChatMarkdown(text: string): string {
  return text
    .replace(/^[ \t]*[•·▪–][ \t]+/gm, "- ")
    .replace(/^([ \t]*(?:[-*]|\d+\.)[ \t].*)\n(?![ \t]*(?:[-*]|\d+\.)[ \t]|\n)/gm, "$1\n\n") // texto após a lista
    .replace(/([^\n])\n(?!\n|[ \t]*(?:[-*]|\d+\.)[ \t])/g, "$1  \n");
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown allowedElements={["p", "strong", "em", "ul", "ol", "li", "br"]} unwrapDisallowed>
        {normalizeChatMarkdown(children)}
      </ReactMarkdown>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}
