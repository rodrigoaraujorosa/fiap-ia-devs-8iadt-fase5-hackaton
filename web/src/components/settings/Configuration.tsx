"use client";

import { AlertTriangle, Check, DatabaseZap, Moon, Play, Send } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { CHAT_STORAGE_KEY } from "@/components/chat/ChatApp";
import { Card } from "@/components/ui";
import { apiGet, apiPost, apiPut, type DemoResetResult, type FollowupConfig, type Metrics } from "@/lib/api";

type Feedback = { tone: "ok" | "error"; text: string } | null;

function Switch({ checked, onChange, label, disabled }: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-50 ${
        checked ? "bg-brand" : "bg-line"
      }`}
    >
      <span
        className={`inline-block size-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5.5" : "translate-x-0.5"}`}
      />
    </button>
  );
}

function Field({ label, hint, htmlFor, children }: { label: string; hint?: ReactNode; htmlFor: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

function FeedbackLine({ feedback }: { feedback: Feedback }) {
  if (!feedback) return null;
  const Icon = feedback.tone === "ok" ? Check : AlertTriangle;
  return (
    <p role="status" className={`flex items-center gap-1.5 text-sm ${feedback.tone === "ok" ? "text-good" : "text-danger"}`}>
      <Icon className="size-4" aria-hidden />
      {feedback.text}
    </p>
  );
}

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50";
const buttonClass =
  "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

function cadence(config: FollowupConfig): string {
  return Array.from({ length: config.max_attempts }, (_, i) => `${config.minutes * 2 ** i} min`).join(" → ");
}

function isValid(c: FollowupConfig): boolean {
  return (
    Number.isInteger(c.minutes) && c.minutes >= 1 && c.minutes <= 1440 &&
    Number.isInteger(c.max_attempts) && c.max_attempts >= 1 && c.max_attempts <= 5 &&
    /^\d{2}:\d{2}$/.test(c.quiet_start) && /^\d{2}:\d{2}$/.test(c.quiet_end)
  );
}

function FollowupSettings() {
  const [saved, setSaved] = useState<FollowupConfig | null>(null);
  const [draft, setDraft] = useState<FollowupConfig | null>(null);
  const [awaiting, setAwaiting] = useState<number | null>(null);
  const [busy, setBusy] = useState<"toggle" | "save" | "run" | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const [config, metrics] = await Promise.all([
        apiGet<FollowupConfig>("/config/followup"),
        apiGet<Metrics>("/dashboard/metrics"),
      ]);
      setSaved(config);
      setDraft((current) => current ?? config);
      setAwaiting(metrics.awaiting_followup);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(load, 0);
    const timer = window.setInterval(load, 10_000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load]);

  async function persist(next: FollowupConfig, kind: "toggle" | "save", message: string) {
    setBusy(kind);
    setFeedback(null);
    try {
      const result = await apiPut<FollowupConfig>("/config/followup", next);
      setSaved(result);
      setFeedback({ tone: "ok", text: message });
      return result;
    } catch {
      setFeedback({ tone: "error", text: "Não foi possível salvar. Verifique se a API está no ar." });
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function toggle(enabled: boolean) {
    if (!saved) return;
    // salva só o liga/desliga, preservando edições ainda não salvas nos outros campos
    const result = await persist({ ...saved, enabled }, "toggle",
      enabled ? "Follow-up ligado: os envios voltam no próximo ciclo (até 30s)." : "Follow-up pausado: nenhuma mensagem automática será enviada.");
    if (result) setDraft((d) => (d ? { ...d, enabled: result.enabled } : d));
  }

  async function runNow() {
    setBusy("run");
    setFeedback(null);
    try {
      const { enviados } = await apiPost<{ enviados: number }>("/followups/run");
      setFeedback({
        tone: "ok",
        text: enviados ? `${enviados} follow-up(s) enviado(s) agora.` : "Nenhum lead com follow-up vencido neste momento.",
      });
      load();
    } catch {
      setFeedback({ tone: "error", text: "Falha ao rodar o follow-up." });
    } finally {
      setBusy(null);
    }
  }

  if (failed && !saved) {
    return (
      <Card title="Follow-up automático">
        <p className="text-sm text-danger">Não consegui carregar a configuração. A API está rodando?</p>
      </Card>
    );
  }
  if (!saved || !draft) {
    return (
      <Card title="Follow-up automático">
        <div className="h-48 animate-pulse rounded-lg bg-surface-2" />
      </Card>
    );
  }

  const dirty = (["minutes", "max_attempts", "quiet_hours", "quiet_start", "quiet_end"] as const).some(
    (k) => draft[k] !== saved[k],
  );
  const valid = isValid(draft);
  const set = <K extends keyof FollowupConfig>(key: K, value: FollowupConfig[K]) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  return (
    <Card title="Follow-up automático">
      <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-2 p-3">
        <div>
          <p className="text-sm font-medium text-ink">Enviar follow-ups automaticamente</p>
          <p className="mt-0.5 text-sm text-ink-2">
            {saved.enabled ? (
              <>
                <span className="font-medium text-good">Ativo.</span> A Laris retoma o contato com leads que pararam de
                responder.
              </>
            ) : (
              <>
                <span className="font-medium text-warm">Pausado.</span> Nenhuma mensagem automática será enviada até você
                religar.
              </>
            )}
            {awaiting !== null && ` ${awaiting} lead(s) com follow-up programado.`}
          </p>
        </div>
        <Switch checked={saved.enabled} onChange={toggle} label="Enviar follow-ups automaticamente" disabled={busy !== null} />
      </div>

      <form
        className="mt-4 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid && dirty) persist({ ...draft, enabled: saved.enabled }, "save", "Configuração salva: vale no próximo ciclo (até 30s).");
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Primeira tentativa após (minutos)" htmlFor="fu-minutes" hint={`Cadência crescente: ${cadence(draft)}`}>
            <input
              id="fu-minutes"
              type="number"
              min={1}
              max={1440}
              inputMode="numeric"
              value={Number.isNaN(draft.minutes) ? "" : draft.minutes}
              onChange={(e) => set("minutes", e.target.valueAsNumber)}
              className={inputClass}
            />
          </Field>
          <Field label="Máximo de tentativas" htmlFor="fu-attempts" hint="Sem resposta depois disso, o lead vira Perdido.">
            <select
              id="fu-attempts"
              value={draft.max_attempts}
              onChange={(e) => set("max_attempts", Number(e.target.value))}
              className={inputClass}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} {n === 1 ? "tentativa" : "tentativas"}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="rounded-lg border border-line p-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
                <Moon className="size-4 text-muted" aria-hidden /> Horário de silêncio
              </p>
              <p className="mt-0.5 text-sm text-ink-2">
                Não envia follow-ups nesse intervalo; os pendentes saem quando ele terminar.
              </p>
            </div>
            <Switch checked={draft.quiet_hours} onChange={(v) => set("quiet_hours", v)} label="Horário de silêncio" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:max-w-sm">
            <Field label="Das" htmlFor="fu-quiet-start">
              <input
                id="fu-quiet-start"
                type="time"
                value={draft.quiet_start}
                disabled={!draft.quiet_hours}
                onChange={(e) => set("quiet_start", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Até" htmlFor="fu-quiet-end">
              <input
                id="fu-quiet-end"
                type="time"
                value={draft.quiet_end}
                disabled={!draft.quiet_hours}
                onChange={(e) => set("quiet_end", e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <button type="submit" disabled={!dirty || !valid || busy !== null} className={`${buttonClass} bg-brand text-white hover:opacity-90`}>
            {busy === "save" ? "Salvando…" : "Salvar alterações"}
          </button>
          {dirty && (
            <button type="button" onClick={() => setDraft(saved)} className={`${buttonClass} text-ink-2 hover:bg-surface-2`}>
              Descartar
            </button>
          )}
          <button
            type="button"
            onClick={runNow}
            disabled={busy !== null}
            className={`${buttonClass} ml-auto border border-line text-ink hover:bg-surface-2`}
            title="Gera com IA e envia agora os follow-ups vencidos, mesmo com o envio automático pausado"
          >
            {busy === "run" ? <Send className="size-4 animate-pulse" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {busy === "run" ? "Enviando…" : "Rodar follow-up agora"}
          </button>
        </div>
        {!valid && <FeedbackLine feedback={{ tone: "error", text: "Use de 1 a 1440 minutos e horários no formato HH:MM." }} />}
        <FeedbackLine feedback={feedback} />
      </form>
    </Card>
  );
}

function DemoReset() {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DemoResetResult | null>(null);
  const [failed, setFailed] = useState(false);

  async function reset() {
    setBusy(true);
    setFailed(false);
    try {
      setResult(await apiPost<DemoResetResult>("/admin/demo/reset"));
      try {
        window.localStorage.removeItem(CHAT_STORAGE_KEY); // a conversa salva no chat deixou de existir
      } catch {}
      setConfirming(false);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Dados de demonstração">
      <p className="text-sm text-ink-2">
        Recria um cenário realista para apresentar a POC: 8 leads em todas as etapas do funil (com conversas, resumos
        para o corretor e 2 agendamentos), agenda dos corretores renovada e 2 leads com follow-up programado para
        disparar nos próximos minutos.
      </p>
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-ink-2">
        <li>
          <strong className="font-medium text-ink">Apaga</strong> todos os leads, conversas, resumos, agendamentos e a
          memória dos agentes.
        </li>
        <li>
          <strong className="font-medium text-ink">Mantém</strong> os imóveis, os embeddings, os corretores e as
          configurações.
        </li>
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!confirming ? (
          <button
            type="button"
            onClick={() => {
              setConfirming(true);
              setResult(null);
            }}
            className={`${buttonClass} border border-danger/40 text-danger hover:bg-danger/10`}
          >
            <DatabaseZap className="size-4" aria-hidden /> Resetar dados de demo
          </button>
        ) : (
          <div role="alertdialog" aria-labelledby="reset-confirm" className="flex flex-wrap items-center gap-2 rounded-lg bg-danger/10 p-2">
            <p id="reset-confirm" className="px-1 text-sm font-medium text-danger">
              Apagar todos os leads atuais e recriar a demo?
            </p>
            <button type="button" onClick={reset} disabled={busy} className={`${buttonClass} bg-danger text-white hover:opacity-90`}>
              {busy ? "Resetando…" : "Sim, resetar"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={busy}
              className={`${buttonClass} text-ink-2 hover:bg-surface`}
              autoFocus
            >
              Cancelar
            </button>
          </div>
        )}
      </div>
      {result && (
        <p role="status" className="mt-3 flex flex-wrap items-center gap-1.5 text-sm text-good">
          <Check className="size-4" aria-hidden />
          Pronto: {result.leads} leads e {result.appointments} agendamentos criados.
          <Link href="/dashboard" className="font-medium text-brand underline-offset-2 hover:underline">
            Abrir o dashboard
          </Link>
        </p>
      )}
      {failed && <FeedbackLine feedback={{ tone: "error", text: "Falha ao resetar os dados. Veja os logs da API." }} />}
    </Card>
  );
}

export function Configuration() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Configurações</h1>
        <p className="text-sm text-ink-2">Ajustes que valem na hora, sem reiniciar a API. O .env define só os valores iniciais.</p>
      </div>
      <FollowupSettings />
      <DemoReset />
    </div>
  );
}
