import type { Metadata } from "next";

import { ChatApp } from "@/components/chat/ChatApp";
import type { LeadSource } from "@/lib/api";

export const metadata: Metadata = { title: "Chat · Laris", robots: { index: false } };

const PROPERTY_CODE = /^IMV-\d{3}$/;
const SOURCE_KEYS = ["page_url", "page_title", "referrer", "utm_source", "utm_medium", "utm_campaign"] as const;

function text(value: string | string[] | undefined, max: number): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v ? v.slice(0, max) : undefined;
}

/** Chat que roda dentro do iframe do widget (public/widget.js), no site de uma imobiliária. */
export default async function EmbedPage({ searchParams }: PageProps<"/embed">) {
  const params = await searchParams;
  const brand = text(params.brand, 80) ?? "ImobiQ";
  const property = text(params.property, 10);
  const source: LeadSource = { brand };
  for (const key of SOURCE_KEYS) {
    const v = text(params[key], 500);
    if (v) source[key] = v;
  }
  if (property && PROPERTY_CODE.test(property)) source.property_id = property;

  let hostOrigin: string | null = null;
  try {
    hostOrigin = params.host ? new URL(text(params.host, 200)!).origin : null;
  } catch {
    hostOrigin = null;
  }

  const draft = text(params.draft, 2000);
  return <ChatApp embed={{ brand, leadId: text(params.lead, 40) ?? null, hostOrigin, source, draft }} />;
}
