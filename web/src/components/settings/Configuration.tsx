"use client";

import { AlertTriangle, Check, DatabaseZap, ExternalLink, FlaskConical, Mail, Moon, Play, Send } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { CHAT_STORAGE_KEY } from "@/components/chat/ChatApp";
import { Card } from "@/components/ui";
import {
  apiGet,
  apiPost,
  apiPut,
  type DemoResetResult,
  type EmailConfig,
  type EmailConfigOut,
  type FollowupConfig,
  type Metrics,
  type TelegramConfig,
  type TelegramConfigOut,
} from "@/lib/api";

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

const MAILPIT_URL = "http://localhost:8025";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function EmailSettings() {
  const [saved, setSaved] = useState<EmailConfigOut | null>(null);
  const [recipient, setRecipient] = useState("");
  const [busy, setBusy] = useState<"toggle" | "save" | "test" | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const first = window.setTimeout(async () => {
      try {
        const config = await apiGet<EmailConfigOut>("/config/email");
        setSaved(config);
        setRecipient(config.demo_recipient);
      } catch {
        setFailed(true);
      }
    }, 0);
    return () => window.clearTimeout(first);
  }, []);

  async function persist(next: EmailConfig, kind: "toggle" | "save", message: string) {
    setBusy(kind);
    setFeedback(null);
    try {
      const result = await apiPut<EmailConfigOut>("/config/email", next);
      setSaved(result);
      setRecipient(result.demo_recipient);
      setFeedback({ tone: "ok", text: message });
    } catch {
      setFeedback({ tone: "error", text: "Não foi possível salvar. Confira o e-mail informado." });
    } finally {
      setBusy(null);
    }
  }

  async function sendTest() {
    setBusy("test");
    setFeedback(null);
    try {
      const { enviado_para } = await apiPost<{ enviado_para: string }>("/config/email/test");
      setFeedback({ tone: "ok", text: `E-mail de teste enviado para ${enviado_para}.` });
    } catch {
      setFeedback({ tone: "error", text: "Falha no envio de teste. Confira as variáveis SMTP no .env e os logs da API." });
    } finally {
      setBusy(null);
    }
  }

  if (failed && !saved) {
    return (
      <Card title="E-mail aos corretores">
        <p className="text-sm text-danger">Não consegui carregar a configuração. A API está rodando?</p>
      </Card>
    );
  }
  if (!saved) {
    return (
      <Card title="E-mail aos corretores">
        <div className="h-40 animate-pulse rounded-lg bg-surface-2" />
      </Card>
    );
  }

  const config: EmailConfig = { enabled: saved.enabled, demo_mode: saved.demo_mode, demo_recipient: saved.demo_recipient };
  const recipientDirty = recipient.trim() !== saved.demo_recipient;
  const recipientValid = EMAIL_RE.test(recipient.trim());
  const smtp = saved.smtp;

  return (
    <Card title="E-mail aos corretores">
      <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-2 p-3">
        <div>
          <p className="text-sm font-medium text-ink">Enviar o resumo ao corretor</p>
          <p className="mt-0.5 text-sm text-ink-2">
            {saved.enabled ? (
              <>
                <span className="font-medium text-good">Ativo.</span> Ao agendar ou encaminhar um lead, o corretor recebe o
                briefing com o convite de calendário.
              </>
            ) : (
              <>
                <span className="font-medium text-warm">Pausado.</span> Nenhum e-mail automático. O envio manual pelo
                detalhe do lead continua disponível.
              </>
            )}
          </p>
        </div>
        <Switch
          checked={saved.enabled}
          label="Enviar o resumo ao corretor"
          disabled={busy !== null}
          onChange={(enabled) =>
            persist({ ...config, enabled }, "toggle", enabled ? "Envio de e-mails ligado." : "Envio de e-mails pausado.")
          }
        />
      </div>

      <div className="mt-4 rounded-lg border border-line p-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
              <FlaskConical className="size-4 text-muted" aria-hidden /> Modo demonstração
            </p>
            <p className="mt-0.5 text-sm text-ink-2">
              {saved.demo_mode
                ? "Todos os e-mails vão para a caixa abaixo; o corretor de destino aparece no assunto."
                : "Cada e-mail vai para o endereço do corretor. Endereços fictícios (.example) não recebem envio."}
            </p>
          </div>
          <Switch
            checked={saved.demo_mode}
            label="Modo demonstração"
            disabled={busy !== null}
            onChange={(demo_mode) =>
              persist(
                { ...config, demo_mode },
                "toggle",
                demo_mode ? "Modo demonstração ligado." : "Modo demonstração desligado: envio aos corretores.",
              )
            }
          />
        </div>
        <form
          className="mt-3 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (recipientDirty && recipientValid)
              persist({ ...config, demo_recipient: recipient.trim() }, "save", "Caixa de demonstração atualizada.");
          }}
        >
          <div className="min-w-56 flex-1">
            <Field label="Caixa de demonstração" htmlFor="email-demo">
              <input
                id="email-demo"
                type="email"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className={inputClass}
                autoComplete="email"
              />
            </Field>
          </div>
          {recipientDirty && (
            <button
              type="submit"
              disabled={!recipientValid || busy !== null}
              className={`${buttonClass} bg-brand text-white hover:opacity-90`}
            >
              {busy === "save" ? "Salvando…" : "Salvar"}
            </button>
          )}
        </form>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-4">
        <div className="w-full min-w-0 text-sm text-ink-2 sm:w-auto sm:flex-1">
          <p className="flex items-center gap-1.5">
            <Mail className="size-4 shrink-0 text-muted" aria-hidden />
            <span className="break-all">
              {smtp.host}:{smtp.port} · {smtp.security}
              {smtp.authenticated ? " · autenticado" : ""}
            </span>
          </p>
          <p className="mt-0.5 break-all text-xs text-muted">Remetente: {smtp.sender}</p>
          {smtp.local_test_inbox && (
            <p className="mt-0.5 text-xs text-muted">
              Caixa de teste local: os e-mails não saem de verdade.{" "}
              <a
                href={MAILPIT_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-0.5 font-medium text-brand underline-offset-2 hover:underline"
              >
                Abrir o Mailpit <ExternalLink className="size-3" aria-hidden />
              </a>
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={sendTest}
          disabled={busy !== null}
          className={`${buttonClass} border border-line text-ink hover:bg-surface-2`}
        >
          <Send className={`size-4 ${busy === "test" ? "animate-pulse" : ""}`} aria-hidden />
          {busy === "test" ? "Enviando…" : "Enviar e-mail de teste"}
        </button>
      </div>
      <div className="mt-2">
        <FeedbackLine feedback={feedback} />
      </div>
    </Card>
  );
}

function TelegramSettings() {
  const [saved, setSaved] = useState<TelegramConfigOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setSaved(await apiGet<TelegramConfigOut>("/config/telegram"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(load, 0);
    const timer = window.setInterval(load, 15_000); // a situação da conexão muda sozinha (ex.: rede)
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load]);

  async function toggle(enabled: boolean) {
    setBusy(true);
    setFeedback(null);
    try {
      setSaved(await apiPut<TelegramConfigOut>("/config/telegram", { enabled } satisfies TelegramConfig));
      setFeedback({ tone: "ok", text: enabled ? "Bot do Telegram ligado." : "Bot do Telegram pausado." });
    } catch {
      setFeedback({ tone: "error", text: "Não foi possível salvar." });
    } finally {
      setBusy(false);
    }
  }

  if (failed && !saved) {
    return (
      <Card title="Bot do Telegram">
        <p className="text-sm text-danger">Não consegui carregar a configuração. A API está rodando?</p>
      </Card>
    );
  }
  if (!saved) {
    return (
      <Card title="Bot do Telegram">
        <div className="h-28 animate-pulse rounded-lg bg-surface-2" />
      </Card>
    );
  }
  if (!saved.configured) {
    return (
      <Card title="Bot do Telegram">
        <p className="text-sm text-ink-2">
          Nenhum bot configurado. Crie um bot no <strong className="font-medium text-ink">@BotFather</strong> e coloque o
          token no <code className="rounded bg-surface-2 px-1">.env</code> como{" "}
          <code className="rounded bg-surface-2 px-1">TELEGRAM_BOT_TOKEN</code>; depois reinicie a API.
        </p>
      </Card>
    );
  }

  const connected = saved.status === "conectado";
  const statusTone = connected ? "text-good" : saved.status.startsWith("erro") ? "text-danger" : "text-warm";
  return (
    <Card title="Bot do Telegram">
      <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-2 p-3">
        <div>
          <p className="text-sm font-medium text-ink">Atender pelo Telegram</p>
          <p className="mt-0.5 text-sm text-ink-2">
            {saved.enabled ? (
              <>
                <span className="font-medium text-good">Ativo.</span> A Laris responde no Telegram com a mesma memória e
                qualificação do chat, e os follow-ups desses leads chegam por lá.
              </>
            ) : (
              <>
                <span className="font-medium text-warm">Pausado.</span> O bot não responde e os follow-ups não são
                entregues no Telegram.
              </>
            )}
          </p>
        </div>
        <Switch checked={saved.enabled} label="Atender pelo Telegram" disabled={busy} onChange={toggle} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-line pt-4">
        {saved.link && (
          <Image
            src={`https://api.qrserver.com/v1/create-qr-code/?size=240x240&margin=8&data=${encodeURIComponent(saved.link)}`}
            alt={`QR code para abrir @${saved.username} no Telegram`}
            width={96}
            height={96}
            unoptimized
            className="rounded-lg border border-line bg-white"
          />
        )}
        <div className="min-w-0 flex-1 space-y-1 text-sm text-ink-2">
          <p className="flex items-center gap-1.5">
            <Send className="size-4 shrink-0 text-muted" aria-hidden />
            {saved.username ? (
              <a
                href={saved.link ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-0.5 font-medium text-brand underline-offset-2 hover:underline"
              >
                @{saved.username} <ExternalLink className="size-3" aria-hidden />
              </a>
            ) : (
              <span>bot ainda não identificado</span>
            )}
          </p>
          <p>
            Conexão: <span className={`font-medium ${statusTone}`}>{saved.status}</span> ·{" "}
            {saved.mode === "webhook" ? "webhook (produção)" : "polling (local, sem URL pública)"}
          </p>
          <p className="text-xs text-muted">Aponte a câmera do celular para o QR code para abrir o bot na demo.</p>
        </div>
      </div>
      <div className="mt-2">
        <FeedbackLine feedback={feedback} />
      </div>
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
          <strong className="font-medium text-ink">Apaga</strong> todos os leads, conversas, resumos, agendamentos, e-mails enviados e a
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
      <EmailSettings />
      <TelegramSettings />
      <DemoReset />
    </div>
  );
}
