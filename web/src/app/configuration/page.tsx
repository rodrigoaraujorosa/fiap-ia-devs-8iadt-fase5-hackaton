import type { Metadata } from "next";

import { Configuration } from "@/components/settings/Configuration";

export const metadata: Metadata = { title: "Configurações · ImobiQ" };

export default function ConfigurationPage() {
  return <Configuration />;
}
