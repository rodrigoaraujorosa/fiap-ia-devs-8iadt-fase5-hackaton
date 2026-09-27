/**
 * Domínios que podem embutir o widget (tela de configurações da API), usados no servidor do app web:
 * a regra frame-ancestors do /embed (o navegador bloqueia o iframe em outros sites) e a rota /widget-policy
 * (o widget.js nem mostra a bolha num site não autorizado).
 */

export type WidgetPolicy = { restrict: boolean; allowed_domains: string[] };

const API = process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const TTL_MS = 30_000;
let cache: { at: number; policy: WidgetPolicy } | null = null;

/** Política atual (renovada a cada 30s). Se a API não responder, vale a última conhecida. */
export async function getWidgetPolicy(): Promise<WidgetPolicy | null> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.policy;
  try {
    const res = await fetch(`${API}/widget/policy`, { cache: "no-store", signal: AbortSignal.timeout(2000) });
    if (res.ok) cache = { at: Date.now(), policy: (await res.json()) as WidgetPolicy };
  } catch {
    /* API fora do ar: mantém a política anterior */
  }
  return cache?.policy ?? null;
}

/** host = "site.com.br" ou "localhost:5500"; "*.site.com.br" na lista vale para os subdomínios e o próprio domínio. */
export function allowsHost(policy: WidgetPolicy | null, host: string): boolean {
  if (!policy?.restrict) return true;
  const h = host.toLowerCase();
  return policy.allowed_domains.some((d) =>
    d.startsWith("*.") ? h === d.slice(2) || h.endsWith(d.slice(1)) : h === d,
  );
}

export function frameAncestors(policy: WidgetPolicy): string {
  const sources = policy.allowed_domains.flatMap((d) => {
    const hosts = d.startsWith("*.") ? [d, d.slice(2)] : [d];
    return hosts.flatMap((h) => [`https://${h}`, `http://${h}`]);
  });
  return ["'self'", ...sources].join(" ");
}
