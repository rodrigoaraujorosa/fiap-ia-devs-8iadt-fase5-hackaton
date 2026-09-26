import { ArrowUpToLine, BedDouble, Building2, Car, Handshake, Ruler, Store, TrainFront, TrendingUp, Truck } from "lucide-react";
import type { ReactNode } from "react";

import type { Property } from "@/lib/api";
import { brl } from "@/lib/format";

function Spec({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="inline-flex items-center gap-1">
      {icon}
      {children}
    </li>
  );
}

/** Atributo que mais importa em cada tipo de imóvel comercial (andar, docas, fachada...). */
function keySpecs(p: Property): ReactNode[] {
  const f = p.features ?? {};
  const specs: ReactNode[] = [];
  if (p.segment === "residencial") {
    specs.push(
      <Spec key="q" icon={<BedDouble aria-hidden size={12} />}>
        {p.bedrooms ? `${p.bedrooms} qto${p.bedrooms > 1 ? "s" : ""}` : "Studio"}
      </Spec>,
    );
  }
  if (f.docas) {
    specs.push(
      <Spec key="d" icon={<Truck aria-hidden size={12} />}>
        {f.docas} doca{f.docas > 1 ? "s" : ""}
      </Spec>,
    );
  }
  if (f.pe_direito_m) {
    specs.push(
      <Spec key="pd" icon={<ArrowUpToLine aria-hidden size={12} />}>
        {f.pe_direito_m.toLocaleString("pt-BR")} m pé-direito
      </Spec>,
    );
  }
  if (f.fachada_m) {
    specs.push(
      <Spec key="fa" icon={<Store aria-hidden size={12} />}>
        {f.fachada_m} m de frente
      </Spec>,
    );
  }
  if (f.andar) {
    specs.push(
      <Spec key="an" icon={<Building2 aria-hidden size={12} />}>
        {f.andar}º andar
      </Spec>,
    );
  }
  if (f.andares) {
    specs.push(
      <Spec key="as" icon={<Building2 aria-hidden size={12} />}>
        {f.andares} andares
      </Spec>,
    );
  }
  return specs;
}

export function PropertyCard({ property: p }: { property: Property }) {
  const leased = p.features?.locado;
  return (
    <article className="w-64 shrink-0 rounded-lg border border-line bg-surface p-3 text-left shadow-sm">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-muted">
        <span>{p.id}</span>
        <span>
          {p.property_type} · {p.purpose === "venda" ? "Venda" : "Aluguel"}
        </span>
      </div>
      <h3 className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-ink">{p.title}</h3>
      <p className="text-xs text-ink-2">
        {p.neighborhood} · {p.city === "São Paulo" ? p.zone : p.city}
      </p>
      <p className="mt-2 text-base font-semibold text-ink">
        {brl(p.price)}
        {p.purpose === "aluguel" && <span className="text-xs font-normal text-ink-2">/mês</span>}
      </p>
      {(p.condo_fee || p.iptu) && (
        <p className="text-[11px] text-muted">
          {p.condo_fee ? `Cond. ${brl(p.condo_fee)}` : ""}
          {p.condo_fee && p.iptu ? " · " : ""}
          {p.iptu ? `IPTU ${brl(p.iptu)}` : ""}
        </p>
      )}
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-2">
        <Spec icon={<Ruler aria-hidden size={12} />}>{p.area_m2.toLocaleString("pt-BR")} m²</Spec>
        {keySpecs(p)}
        {p.parking > 0 && (
          <Spec icon={<Car aria-hidden size={12} />}>
            {p.parking} vaga{p.parking > 1 ? "s" : ""}
          </Spec>
        )}
        {p.near_metro && <Spec icon={<TrainFront aria-hidden size={12} />}>Metrô</Spec>}
      </ul>
      {!!p.features?.atividades?.length && (
        <p className="mt-2 text-[11px] text-muted">Permite: {p.features.atividades.join(", ")}</p>
      )}
      {leased && (
        <p className="mt-2 flex items-start gap-1 text-xs text-ink">
          <Handshake aria-hidden size={13} className="mt-0.5 shrink-0 text-brand" />
          <span>
            Locado para {leased.inquilino} até {leased.contrato_ate} · {brl(leased.aluguel_atual)}/mês
          </span>
        </p>
      )}
      {p.estimated_yield && (
        <p className="mt-2 inline-flex items-center gap-1 rounded-md bg-brand-soft px-2 py-0.5 text-xs font-medium text-ink">
          <TrendingUp aria-hidden size={12} /> {p.estimated_yield.toLocaleString("pt-BR")}% a.a. estimado
        </p>
      )}
    </article>
  );
}
