import Link from "next/link";
import type { ReactNode } from "react";

/** Dados de quem responde pelo ImobiQ, usados na Política de Privacidade e nos Termos de Uso. */
export const LEGAL = {
  owner: "Rodrigo de Araujo Rosa",
  email: "rodrigo@arrtsoftware.com.br",
  team: "Elias Silva, Fabia de Jesus e Danilo Pereira (Grupo 65)",
  site: "https://imobiq.arrtsoftware.com.br",
  updated: "4 de outubro de 2026",
};

export function Contact() {
  return (
    <a href={`mailto:${LEGAL.email}`} className="font-medium text-brand underline-offset-2 hover:underline">
      {LEGAL.email}
    </a>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="pt-2 text-lg font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

export function List({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-1 pl-5">{children}</ul>;
}

/** Página de texto legal (privacidade, termos): coluna de leitura, com a data da última atualização. */
export function LegalPage({ title, intro, children }: { title: string; intro: ReactNode; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-4 text-sm leading-relaxed text-ink-2">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        <p className="text-xs text-muted">Última atualização: {LEGAL.updated}</p>
        <p>{intro}</p>
      </header>
      {children}
      <p className="border-t border-line pt-4 text-xs text-muted">
        Veja também: <Link href="/privacidade" className="underline-offset-2 hover:underline">Política de Privacidade</Link>
        {" · "}
        <Link href="/termos" className="underline-offset-2 hover:underline">Termos de Uso</Link>
      </p>
    </article>
  );
}
