"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState, type ComponentProps } from "react";

import { inputClass } from "@/components/settings/controls";

/** Campo de senha com o botão do olho, para mostrar ou ocultar o que foi digitado. */
export function PasswordInput(props: Omit<ComponentProps<"input">, "type" | "className">) {
  const [visible, setVisible] = useState(false);
  const Icon = visible ? EyeOff : Eye;
  return (
    <div className="relative">
      <input {...props} type={visible ? "text" : "password"} className={`${inputClass} pr-10`} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
        aria-pressed={visible}
        title={visible ? "Ocultar senha" : "Mostrar senha"}
        className="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-lg text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-brand"
      >
        <Icon className="size-4" aria-hidden />
      </button>
    </div>
  );
}
