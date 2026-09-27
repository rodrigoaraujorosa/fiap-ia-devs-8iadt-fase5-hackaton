"use client";

import { Gauge, Globe } from "lucide-react";
import { useEffect, useState } from "react";

import { FeedbackLine, Field, Switch, buttonClass, inputClass, type Feedback } from "@/components/settings/controls";
import { Card } from "@/components/ui";
import { ApiError, apiGet, apiPut, type RateLimitConfig, type WidgetConfig } from "@/lib/api";

type LimitKey = Exclude<keyof RateLimitConfig, "enabled">;

const LIMIT_FIELDS: { key: LimitKey; label: string; hint: string; min: number; max: number }[] = [
  {
    key: "conversation_hour",
    label: "Mensagens por conversa (por hora)",
    hint: "Uma pessoa conversando normalmente manda de 10 a 20.",
    min: 5,
    max: 500,
  },
  {
    key: "ip_hour",
    label: "Mensagens por IP (por hora)",
    hint: "Soma as conversas abertas da mesma conexão.",
    min: 5,
    max: 2000,
  },
  {
    key: "sessions_ip_hour",
    label: "Conversas novas por IP (por hora)",
    hint: "Evita abrir conversas em série para driblar o limite.",
    min: 1,
    max: 500,
  },
  {
    key: "daily_total",
    label: "Teto diário de mensagens (total)",
    hint: "Trava de custo: acima dele, a Laris pausa a IA e pede o contato.",
    min: 10,
    max: 100000,
  },
];

function LoadingCard({ title, failed }: { title: string; failed: boolean }) {
  return (
    <Card title={title}>
      {failed ? (
        <p className="text-sm text-danger">Não consegui carregar a configuração. A API está rodando?</p>
      ) : (
        <div className="h-32 animate-pulse rounded-lg bg-surface-2" />
      )}
    </Card>
  );
}

function RateLimitSettings() {
  const [saved, setSaved] = useState<RateLimitConfig | null>(null);
  const [draft, setDraft] = useState<RateLimitConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    apiGet<RateLimitConfig>("/config/rate-limit")
      .then((c) => {
        setSaved(c);
        setDraft(c);
      })
      .catch(() => setFailed(true));
  }, []);

  async function persist(next: RateLimitConfig, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      const result = await apiPut<RateLimitConfig>("/config/rate-limit", next);
      setSaved(result);
      setDraft((d) => (d ? { ...d, enabled: result.enabled } : result));
      setFeedback({ tone: "ok", text: message });
    } catch {
      setFeedback({ tone: "error", text: "Não foi possível salvar. Confira os valores." });
    } finally {
      setBusy(false);
    }
  }

  if (!saved || !draft) return <LoadingCard title="Limite de mensagens" failed={failed} />;

  const valid = LIMIT_FIELDS.every(
    ({ key, min, max }) => Number.isInteger(draft[key]) && draft[key] >= min && draft[key] <= max,
  );
  const dirty = LIMIT_FIELDS.some(({ key }) => draft[key] !== saved[key]);
  return (
    <Card title="Limite de mensagens">
      <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-2 p-3">
        <div>
          <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
            <Gauge className="size-4 text-muted" aria-hidden /> Limitar o uso do chat
          </p>
          <p className="mt-0.5 text-sm text-ink-2">
            {saved.enabled ? (
              <>
                <span className="font-medium text-good">Ativo.</span> Quem passa do limite recebe um aviso para esperar
                alguns minutos, sem chamar a IA. Vale para o chat, o widget e o Telegram.
              </>
            ) : (
              <>
                <span className="font-medium text-warm">Desligado.</span> Sem limites: qualquer pessoa pode mandar
                mensagens à vontade (e gastar tokens).
              </>
            )}
          </p>
        </div>
        <Switch
          checked={saved.enabled}
          label="Limitar o uso do chat"
          disabled={busy}
          onChange={(enabled) => persist({ ...saved, enabled }, enabled ? "Limites ligados." : "Limites desligados.")}
        />
      </div>
      <form
        className="mt-4 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid && dirty) persist({ ...draft, enabled: saved.enabled }, "Limites salvos: valem na próxima mensagem.");
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {LIMIT_FIELDS.map(({ key, label, hint, min, max }) => (
            <Field key={key} label={label} htmlFor={`rl-${key}`} hint={hint}>
              <input
                id={`rl-${key}`}
                type="number"
                min={min}
                max={max}
                inputMode="numeric"
                value={Number.isNaN(draft[key]) ? "" : draft[key]}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.valueAsNumber })}
                className={inputClass}
              />
            </Field>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <button type="submit" disabled={!dirty || !valid || busy} className={`${buttonClass} bg-brand text-white hover:opacity-90`}>
            {busy ? "Salvando…" : "Salvar limites"}
          </button>
          {dirty && (
            <button type="button" onClick={() => setDraft(saved)} className={`${buttonClass} text-ink-2 hover:bg-surface-2`}>
              Descartar
            </button>
          )}
        </div>
        {!valid && (
          <FeedbackLine feedback={{ tone: "error", text: "Confira os valores: use números inteiros dentro dos limites." }} />
        )}
        <FeedbackLine feedback={feedback} />
      </form>
    </Card>
  );
}

function WidgetSettings() {
  const [saved, setSaved] = useState<WidgetConfig | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    apiGet<WidgetConfig>("/config/widget")
      .then((c) => {
        setSaved(c);
        setText(c.allowed_domains.join("\n"));
      })
      .catch(() => setFailed(true));
  }, []);

  const domains = text
    .split(/[\n,]/)
    .map((d) => d.trim())
    .filter(Boolean);

  async function persist(next: WidgetConfig, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      const result = await apiPut<WidgetConfig>("/config/widget", next);
      setSaved(result);
      setText(result.allowed_domains.join("\n"));
      setFeedback({ tone: "ok", text: message });
    } catch (err) {
      const invalid = err instanceof ApiError && err.status === 422;
      setFeedback({ tone: "error", text: invalid ? "Há um domínio inválido na lista." : "Não foi possível salvar." });
    } finally {
      setBusy(false);
    }
  }

  if (!saved) return <LoadingCard title="Domínios do widget" failed={failed} />;

  const dirty = domains.join("\n") !== saved.allowed_domains.join("\n");
  return (
    <Card title="Domínios do widget">
      <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-2 p-3">
        <div>
          <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
            <Globe className="size-4 text-muted" aria-hidden /> Só abrir o widget nos sites da lista
          </p>
          <p className="mt-0.5 text-sm text-ink-2">
            {saved.restrict ? (
              <>
                <span className="font-medium text-good">Ativo.</span> Em outro site a bolha da Laris não aparece e o
                navegador bloqueia o chat embutido. Mudanças valem em até 30 segundos.
              </>
            ) : (
              <>
                <span className="font-medium text-warm">Liberado.</span> Qualquer site que copiar a linha do script
                consegue mostrar a Laris.
              </>
            )}
          </p>
        </div>
        <Switch
          checked={saved.restrict}
          label="Só abrir o widget nos sites da lista"
          disabled={busy || (!saved.restrict && !saved.allowed_domains.length)}
          onChange={(restrict) =>
            persist({ ...saved, restrict }, restrict ? "Widget restrito aos domínios da lista." : "Widget liberado em qualquer site.")
          }
        />
      </div>
      <form
        className="mt-4 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (dirty) persist({ ...saved, allowed_domains: domains }, "Lista de domínios salva.");
        }}
      >
        <Field
          label="Domínios autorizados"
          htmlFor="widget-domains"
          hint={
            <>
              Um por linha, com a porta se houver. <code className="rounded bg-surface-2 px-1">*.imobiliaria.com.br</code>{" "}
              vale para todos os subdomínios.
            </>
          }
        >
          <textarea
            id="widget-domains"
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"imobiliaria-exemplo.arrtsoftware.com.br\nlocalhost:5500"}
            spellCheck={false}
            className={`${inputClass} font-mono`}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-2">
          <button type="submit" disabled={!dirty || busy} className={`${buttonClass} bg-brand text-white hover:opacity-90`}>
            {busy ? "Salvando…" : "Salvar domínios"}
          </button>
          {dirty && (
            <button
              type="button"
              onClick={() => setText(saved.allowed_domains.join("\n"))}
              className={`${buttonClass} text-ink-2 hover:bg-surface-2`}
            >
              Descartar
            </button>
          )}
        </div>
        {saved.restrict && !domains.length && (
          <FeedbackLine
            feedback={{ tone: "error", text: "Com a restrição ligada e a lista vazia, o widget não abre em nenhum site." }}
          />
        )}
        <FeedbackLine feedback={feedback} />
      </form>
    </Card>
  );
}

export function SecuritySettings() {
  return (
    <>
      <RateLimitSettings />
      <WidgetSettings />
    </>
  );
}
