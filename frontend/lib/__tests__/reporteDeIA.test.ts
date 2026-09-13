// =====================================================================
// El canal para reportar una respuesta generada
// =====================================================================
//
// Microsoft exige dos cosas a una aplicación que entrega texto escrito por un
// modelo: que el usuario sepa que lo es, y que tenga cómo reportar una
// respuesta dañina o inapropiada. Esto es lo segundo.
//
// Lo que vigila esta prueba no es el formato del correo: es que reportar no se
// convierta en una cuarta salida a la red. El producto acaba de cerrar tres que
// salían sin permiso; abrir una más —que además mandaría la conversación— para
// cumplir una obligación de transparencia contradiría el aviso que la acompaña.
// Por eso es un `mailto:` que la persona envía, y no una llamada a un servicio.

import { describe, expect, it } from "vitest";

import {
  CORREO_DE_REPORTE,
  LIMITE_DE_RESPUESTA,
  construirMailtoDeReporte,
  recortar,
} from "../reporteDeIA";

const TEXTOS = {
  asunto: "Reporte de respuesta de MolChat",
  cabecera: "Describe qué tiene de incorrecto:",
  etiquetaRespuesta: "Respuesta reportada",
  etiquetaProveedor: "Proveedor",
};

function cuerpoDe(url: string): string {
  // `mailto:` no es una URL jerárquica; `URL` deja los parámetros en `search`.
  return new URLSearchParams(new URL(url).search).get("body") ?? "";
}

describe("el reporte se abre, no se envía", () => {
  it("es un mailto al contacto de soporte", () => {
    const url = construirMailtoDeReporte(
      { respuesta: "una respuesta", proveedor: "Local" },
      TEXTOS,
    );

    expect(url.startsWith(`mailto:${CORREO_DE_REPORTE}?`)).toBe(true);
  });

  it("no apunta a ningún servicio remoto", () => {
    const url = construirMailtoDeReporte(
      { respuesta: "una respuesta", proveedor: "Local" },
      TEXTOS,
    );

    expect(url).not.toMatch(/^https?:/);
  });

  it("lleva la respuesta y el proveedor ya escritos", () => {
    const url = construirMailtoDeReporte(
      { respuesta: "el modelo dijo algo inapropiado", proveedor: "Claude" },
      TEXTOS,
    );
    const cuerpo = cuerpoDe(url);

    expect(cuerpo).toContain("el modelo dijo algo inapropiado");
    expect(cuerpo).toContain("Proveedor: Claude");
  });

  it("una respuesta con & no parte la URL en dos parámetros", () => {
    // Concatenar en vez de codificar dejaba fuera del cuerpo todo lo que
    // siguiera al primer `&`, que es justo la parte que se está reportando.
    const url = construirMailtoDeReporte(
      { respuesta: "riesgo A & riesgo B", proveedor: "Local" },
      TEXTOS,
    );

    expect(cuerpoDe(url)).toContain("riesgo A & riesgo B");
  });

  it("no deja espacios convertidos en signos de suma", () => {
    const url = construirMailtoDeReporte(
      { respuesta: "dos palabras", proveedor: "Local" },
      TEXTOS,
    );

    expect(url).not.toContain("+");
  });
});

describe("recortar declara que recortó", () => {
  it("deja intacto lo que cabe", () => {
    expect(recortar("corto")).toBe("corto");
  });

  it("avisa del recorte y dice cuánto había", () => {
    // Un cliente de correo trunca un mailto largo en silencio. Un reporte
    // cortado por la mitad sin avisar es peor que uno corto que lo declara.
    const largo = "x".repeat(LIMITE_DE_RESPUESTA + 500);
    const recortado = recortar(largo);

    expect(recortado).toContain("recortado");
    expect(recortado).toContain(String(LIMITE_DE_RESPUESTA + 500));
    expect(recortado.length).toBeLessThan(largo.length);
  });
});
