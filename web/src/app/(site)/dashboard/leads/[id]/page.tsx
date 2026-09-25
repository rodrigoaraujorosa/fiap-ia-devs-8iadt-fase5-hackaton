import type { Metadata } from "next";

import { LeadDetailView } from "@/components/dashboard/LeadDetailView";

export const metadata: Metadata = { title: "Lead · ImobiQ" };

export default async function LeadPage({ params }: PageProps<"/dashboard/leads/[id]">) {
  const { id } = await params;
  return <LeadDetailView id={id} />;
}
