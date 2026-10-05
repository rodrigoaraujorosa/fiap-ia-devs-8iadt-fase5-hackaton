"use client";

import { Check, Copy, KeyRound, Trash2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useSession } from "@/components/Session";
import { FeedbackLine, Field, buttonClass, inputClass, type Feedback } from "@/components/settings/controls";
import { Card } from "@/components/ui";
import {
  ApiError,
  ROLE_LABEL,
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  type AccessLink,
  type BrokerOption,
  type InvitedUser,
  type Role,
  type UserRow,
} from "@/lib/api";

const ROLES: Role[] = ["admin", "gestor", "corretor", "visualizador"];
const ROLE_HINT: Record<Role, string> = {
  admin: "Tudo, inclusive configurações e usuários.",
  gestor: "Todos os leads, a agenda e a observabilidade.",
  corretor: "Só os leads e as visitas do corretor vinculado.",
  visualizador: "Vê tudo o que o gestor vê, sem alterar nada.",
};
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const selectClass = `${inputClass} py-1.5`;

/** Link de acesso recém-gerado: o admin pode copiar e mandar por onde quiser (o e-mail é só um dos caminhos). */
function AccessLinkBox({ email, access }: { email: string; access: AccessLink }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(access.link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface-2 p-3">
      <p className="text-sm text-ink">
        Link para <strong className="font-medium">{email}</strong> criar a senha
        {access.emailed ? " (também enviado por e-mail)" : " (o e-mail não saiu: envie o link você mesmo)"}:
      </p>
      <div className="mt-2 flex items-center gap-2">
        <input readOnly value={access.link} aria-label="Link de acesso" onFocus={(e) => e.target.select()} className={`${inputClass} font-mono text-xs`} />
        <button type="button" onClick={copy} className={`${buttonClass} shrink-0 border border-line text-ink hover:bg-surface`}>
          {copied ? <Check className="size-4 text-good" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <p className="mt-1.5 text-xs text-muted">Vale por 72 horas e uma vez só. Quem tem acesso a este link define a senha da conta.</p>
    </div>
  );
}

/** Quem pode entrar (e-mail e senha ou conta Google) e com qual papel. Só entra quem está nesta lista. */
export function UsersSettings() {
  const { session } = useSession();
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [brokers, setBrokers] = useState<BrokerOption[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("visualizador");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [failed, setFailed] = useState(false);
  const [access, setAccess] = useState<{ email: string; access: AccessLink } | null>(null);

  const load = useCallback(async () => {
    try {
      const [list, options] = await Promise.all([apiGet<UserRow[]>("/users"), apiGet<BrokerOption[]>("/users/brokers")]);
      setUsers(list);
      setBrokers(options);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(load, 0);
    return () => window.clearTimeout(first);
  }, [load]);

  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      setFeedback({ tone: "ok", text: done });
      await load();
    } catch (err) {
      setFeedback({ tone: "error", text: err instanceof ApiError ? err.message : "Não foi possível salvar." });
    } finally {
      setBusy(false);
    }
  }

  async function invite(event: FormEvent) {
    event.preventDefault();
    const address = email.trim().toLowerCase();
    setAccess(null);
    await run(async () => {
      const invited = await apiPost<InvitedUser>("/users", { email: address, role });
      setAccess({ email: invited.email, access: invited.access });
    }, `${address} convidado como ${ROLE_LABEL[role]}.`);
    setEmail("");
  }

  async function newLink(user: UserRow) {
    setAccess(null);
    await run(async () => {
      setAccess({ email: user.email, access: await apiPost<AccessLink>(`/users/${user.id}/access-link`) });
    }, `Novo link de senha gerado para ${user.email}.`);
  }

  if (!users) {
    return (
      <Card title="Usuários e papéis">
        {failed ? (
          <p className="text-sm text-danger">Não consegui carregar os usuários. A API está rodando?</p>
        ) : (
          <div className="h-32 animate-pulse rounded-lg bg-surface-2" />
        )}
      </Card>
    );
  }

  const myEmail = session?.user?.email;
  return (
    <Card title="Usuários e papéis">
      <p className="text-sm text-ink-2">
        Só entra quem está nesta lista, com e-mail e senha
        {session?.google ? " ou com a conta Google do mesmo e-mail" : ""}. O convidado recebe um link para criar a
        própria senha. A mudança de papel vale na próxima ação do usuário.
      </p>

      {users.length === 0 ? (
        <p className="mt-3 rounded-lg bg-surface-2 p-3 text-sm text-ink-2">Nenhum usuário convidado ainda.</p>
      ) : (
        <ul className="mt-3 divide-y divide-line rounded-lg border border-line">
          {users.map((u) => {
            const self = u.email === myEmail;
            return (
              <li key={u.id} className={`flex flex-wrap items-center gap-x-3 gap-y-2 p-3 ${u.active ? "" : "opacity-60"}`}>
                <div className="min-w-0 flex-1 basis-52">
                  <p className="truncate text-sm font-medium text-ink">
                    {u.name ?? u.email} {self && <span className="font-normal text-muted">(você)</span>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {u.name ? `${u.email} · ` : ""}
                    {u.last_login_at
                      ? `último acesso em ${new Date(u.last_login_at).toLocaleDateString("pt-BR")}`
                      : "ainda não entrou"}
                    {u.active && !u.has_password && " · sem senha criada"}
                    {!u.active && " · desativado"}
                  </p>
                </div>
                <select
                  aria-label={`Papel de ${u.email}`}
                  value={u.role}
                  disabled={busy || self}
                  onChange={(e) =>
                    run(() => apiPatch(`/users/${u.id}`, { role: e.target.value }), `Papel de ${u.email} atualizado.`)
                  }
                  className={`${selectClass} w-36`}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABEL[r]}
                    </option>
                  ))}
                </select>
                {u.role === "corretor" && (
                  <select
                    aria-label={`Corretor vinculado a ${u.email}`}
                    value={u.broker_id ?? ""}
                    disabled={busy}
                    onChange={(e) =>
                      run(
                        () => apiPatch(`/users/${u.id}`, { broker_id: e.target.value ? Number(e.target.value) : null }),
                        `Vínculo de ${u.email} atualizado.`,
                      )
                    }
                    className={`${selectClass} w-48 ${u.broker_id ? "" : "border-warm"}`}
                  >
                    <option value="">Vincular a um corretor…</option>
                    {brokers.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  disabled={busy || !u.active}
                  aria-label={`Gerar link de senha para ${u.email}`}
                  title={u.has_password ? "Gerar link para redefinir a senha" : "Gerar novo link para criar a senha"}
                  onClick={() => newLink(u)}
                  className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-40"
                >
                  <KeyRound className="size-4" aria-hidden />
                </button>
                <button
                  type="button"
                  disabled={busy || self}
                  onClick={() =>
                    run(
                      () => apiPatch(`/users/${u.id}`, { active: !u.active }),
                      u.active ? `${u.email} desativado: perde o acesso na hora.` : `${u.email} reativado.`,
                    )
                  }
                  className={`${buttonClass} border border-line px-2.5 py-1.5 text-xs text-ink-2 hover:text-ink`}
                >
                  {u.active ? "Desativar" : "Reativar"}
                </button>
                <button
                  type="button"
                  disabled={busy || self}
                  aria-label={`Excluir ${u.email}`}
                  title="Excluir"
                  onClick={() => run(() => apiDelete(`/users/${u.id}`), `${u.email} excluído.`)}
                  className="rounded-md p-1.5 text-ink-2 hover:bg-danger/10 hover:text-danger disabled:opacity-40"
                >
                  <Trash2 className="size-4" aria-hidden />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <form onSubmit={invite} className="mt-4 flex flex-wrap items-end gap-2 border-t border-line pt-4">
        <div className="min-w-56 flex-1">
          <Field label="Convidar por e-mail" htmlFor="user-email">
            <input
              id="user-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="pessoa@empresa.com.br"
              autoComplete="off"
              className={inputClass}
            />
          </Field>
        </div>
        <div className="w-40">
          <Field label="Papel" htmlFor="user-role">
            <select id="user-role" value={role} onChange={(e) => setRole(e.target.value as Role)} className={inputClass}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <button
          type="submit"
          disabled={busy || !EMAIL_RE.test(email.trim())}
          className={`${buttonClass} bg-brand text-white hover:opacity-90`}
        >
          <UserPlus className="size-4" aria-hidden /> Convidar
        </button>
      </form>
      <p className="mt-2 text-xs text-muted">
        {ROLE_LABEL[role]}: {ROLE_HINT[role]}
      </p>
      <div className="mt-2">
        <FeedbackLine feedback={feedback} />
      </div>
      {access && <AccessLinkBox email={access.email} access={access.access} />}
    </Card>
  );
}
