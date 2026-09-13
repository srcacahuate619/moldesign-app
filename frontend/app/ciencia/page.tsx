"use client";

import { RegistroCientifico } from "@/components/registro/RegistroCientifico";

export default function CienciaPage() {
  return (
    <main style={{ minHeight: "100dvh", background: "var(--bg)", color: "var(--text)" }}>
      <RegistroCientifico />
    </main>
  );
}
