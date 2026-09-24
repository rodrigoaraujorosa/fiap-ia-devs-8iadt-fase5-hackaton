import Link from "next/link";

import { apiGet, brl, type Property } from "@/lib/api";

async function loadStatus() {
  try {
    const [health, properties] = await Promise.all([
      apiGet<{ status: string }>("/health"),
      apiGet<Property[]>("/properties?limit=6"),
    ]);
    return { online: health.status === "ok", properties };
  } catch {
    return { online: false, properties: [] as Property[] };
  }
}

export default async function Home() {
  const { online, properties } = await loadStatus();

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-3xl font-bold">Agente SDR Imobiliário com IA</h1>
        <p className="max-w-2xl opacity-80">
          Atende leads 24/7, qualifica intenção de compra, aluguel ou investimento, sugere imóveis, agenda visitas e
          entrega um resumo pronto para o corretor.
        </p>
        <div className="flex gap-3">
          <Link href="/chat" className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white">
            Conversar com a Lia
          </Link>
          <Link href="/dashboard" className="rounded-md border border-current/20 px-4 py-2 text-sm font-medium">
            Abrir dashboard
          </Link>
        </div>
        <p className="text-sm">
          API:{" "}
          <span className={online ? "text-emerald-600" : "text-red-600"}>{online ? "online" : "offline"}</span>
        </p>
      </section>

      {properties.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Amostra da base de imóveis</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {properties.map((p) => (
              <li key={p.id} className="rounded-lg border border-current/10 p-4">
                <p className="text-xs uppercase opacity-60">
                  {p.id} · {p.purpose} · {p.zone}
                </p>
                <p className="font-medium">{p.title}</p>
                <p className="text-sm opacity-80">
                  {brl(p.price)}
                  {p.purpose === "aluguel" ? "/mês" : ""} · {p.area_m2} m² · {p.bedrooms} qto(s)
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
