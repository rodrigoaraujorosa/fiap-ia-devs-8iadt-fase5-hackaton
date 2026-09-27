import type { Metadata } from "next";

import { Observability } from "@/components/observability/Observability";

export const metadata: Metadata = { title: "Observabilidade · ImobiQ" };

export default function ObservabilityPage() {
  return <Observability />;
}
