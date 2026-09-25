import { BedDouble, Car, Dog, Ruler, TrainFront, TrendingUp } from "lucide-react";

import type { Property } from "@/lib/api";
import { brl } from "@/lib/format";

export function PropertyCard({ property: p }: { property: Property }) {
  return (
    <article className="w-60 shrink-0 rounded-lg border border-line bg-surface p-3 text-left shadow-sm">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-muted">
        <span>{p.id}</span>
        <span>{p.purpose === "venda" ? "Venda" : "Aluguel"}</span>
      </div>
      <h3 className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-ink">{p.title}</h3>
      <p className="text-xs text-ink-2">
        {p.neighborhood} · {p.zone}
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
        <li className="inline-flex items-center gap-1">
          <Ruler aria-hidden size={12} /> {p.area_m2} m²
        </li>
        <li className="inline-flex items-center gap-1">
          <BedDouble aria-hidden size={12} /> {p.bedrooms ? `${p.bedrooms} qto${p.bedrooms > 1 ? "s" : ""}` : "Studio"}
        </li>
        {p.parking > 0 && (
          <li className="inline-flex items-center gap-1">
            <Car aria-hidden size={12} /> {p.parking} vaga{p.parking > 1 ? "s" : ""}
          </li>
        )}
        {p.near_metro && (
          <li className="inline-flex items-center gap-1">
            <TrainFront aria-hidden size={12} /> Metrô
          </li>
        )}
        {p.pet_friendly && (
          <li className="inline-flex items-center gap-1">
            <Dog aria-hidden size={12} /> Pet
          </li>
        )}
      </ul>
      {p.estimated_yield && (
        <p className="mt-2 inline-flex items-center gap-1 rounded-md bg-brand-soft px-2 py-0.5 text-xs font-medium text-ink">
          <TrendingUp aria-hidden size={12} /> {p.estimated_yield.toLocaleString("pt-BR")}% a.a. estimado
        </p>
      )}
    </article>
  );
}
