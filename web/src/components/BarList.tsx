"use client";

import { useState } from "react";

type Row = { key: string; label: string; value: number };

/**
 * Barras horizontais de série única (skill dataviz): barra <= 24px com ponta arredondada de 4px e base reta,
 * valor na ponta em tinta de texto, tooltip por barra (hover e foco) com alvo maior que a marca.
 */
export function BarList({
  rows,
  unit = "leads",
  total,
  format = String,
}: {
  rows: Row[];
  unit?: string;
  total?: number;
  format?: (value: number) => string; // ex.: custo em US$ (a coluna do valor fica mais larga)
}) {
  const wide = format !== String;
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(1, ...rows.map((r) => r.value));
  const sum = total ?? rows.reduce((acc, r) => acc + r.value, 0);

  return (
    <ul className="space-y-1" role="list">
      {rows.map((row, index) => {
        const pct = sum ? Math.round((row.value / sum) * 100) : 0;
        const isActive = active === row.key;
        return (
          <li key={row.key}>
            <button
              type="button"
              className={`group relative grid w-full ${wide ? "grid-cols-[8.5rem_1fr_4.5rem]" : "grid-cols-[7.5rem_1fr_2.5rem]"} items-center gap-2 rounded-md px-1 py-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-data`}
              onPointerEnter={() => setActive(row.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(row.key)}
              onBlur={() => setActive(null)}
              aria-label={`${row.label}: ${row.value} ${unit} (${pct}%)`}
            >
              <span className="truncate text-xs text-ink-2">{row.label}</span>
              <span className="relative h-5">
                <span
                  className={`absolute inset-y-0.5 left-0 rounded-r-[4px] bg-data transition-[width,opacity] duration-500 ${
                    active && !isActive ? "opacity-60" : ""
                  }`}
                  style={{ width: row.value ? `max(4px, ${(row.value / max) * 100}%)` : 0 }}
                />
              </span>
              <span className="tabular text-right text-xs font-medium text-ink">{format(row.value)}</span>
              {isActive && (
                <span
                  role="tooltip"
                  className={`pointer-events-none absolute left-32 z-10 ${index === 0 ? "top-full mt-1" : "bottom-full mb-1"} rounded-md border border-line bg-surface px-2 py-1 text-xs shadow-md`}
                >
                  <strong className="tabular font-semibold text-ink">
                    {format(row.value)} {unit}
                  </strong>{" "}
                  <span className="text-ink-2">
                    · {row.label} · {pct}%
                  </span>
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
