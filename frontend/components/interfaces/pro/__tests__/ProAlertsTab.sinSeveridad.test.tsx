import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cierre } from "@/context/traducciones/cierre";
import { evaluacion } from "@/context/traducciones/evaluacion";
import { ProAlertsTab } from "../ProAlertsTab";

// SCI-A-035. El runner ACTUAL todavía emite algunos avisos como texto suelto
// (el de secuencia peptídica compatible con ESMFold, por ejemplo), y el pie de
// la tarjeta los presentaba como «corrida anterior a la etapa que declara la
// severidad». Un aviso sin severidad no fecha la corrida que lo emitió.

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({
  useLanguage: () => ({
    t: (key: string) => {
      const dicc = { ...cierre[mocks.locale], ...evaluacion[mocks.locale] } as Record<string, string>;
      return dicc[key] ?? key;
    },
  }),
}));

beforeEach(() => {
  mocks.locale = "es";
});

const AVISO_DE_TEXTO = "⚠️ Se detectó una secuencia peptídica lineal compatible con ESMFold.";

describe("aviso sin severidad declarada", () => {
  for (const locale of ["es", "en"] as const) {
    it(`no lo atribuye a una corrida anterior (${locale})`, () => {
      mocks.locale = locale;
      const { container } = render(<ProAlertsTab warnings={[AVISO_DE_TEXTO]} />);
      const texto = container.textContent ?? "";

      expect(screen.getByText(cierre[locale].z_no_severity)).toBeVisible();
      expect(screen.getByText(evaluacion[locale].ev_aviso_sin_severidad_pie)).toBeVisible();
      expect(texto).not.toMatch(/Corrida anterior|earlier run|older run|predates/i);
      // La clave cruda nunca llega a la pantalla.
      expect(texto).not.toContain("ev_aviso_sin_severidad_pie");
    });
  }
});
