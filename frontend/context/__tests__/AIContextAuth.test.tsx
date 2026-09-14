// =====================================================================
// MOLCHAT-BE-002 — el cliente de MolChat envía identidad
// =====================================================================
//
// `AIContext` hacía todas sus llamadas con `fetch` crudo y sin cabeceras, así
// que `current_user` llegaba `None` incluso en `/ai/chat`, el único endpoint
// que la pedía. En la práctica MolChat nunca tuvo identidad de usuario: las
// herramientas resolvían el historial contra el usuario demo.
//
// Esta prueba vigila el lado del cliente. El lado del servidor lo cubre
// `backend/tests/test_ai_endpoints_exigen_sesion.py`.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const aqui = dirname(fileURLToPath(import.meta.url));
const fuente = readFileSync(resolve(aqui, "..", "AIContext.tsx"), "utf8");
const ajustes = readFileSync(
  resolve(aqui, "..", "..", "components", "ai", "AISettingsModal.tsx"),
  "utf8",
);

/** Todas las llamadas `fetch` a `/ai/...` que aparecen en el contexto. */
function llamadasAi(texto: string): string[] {
  const llamadas: string[] = [];
  // El cierre es `);` y no `)` seguido de `;` o `,`: una llamada cuyo cuerpo
  // termina en `getAuthHeaders(),` —la coma de un objeto multilínea— cortaba el
  // trozo antes de la propia cabecera y se denunciaba sola.
  const patron = /fetch\(\s*`\$\{await getApiUrl\(\)\}(\/ai\/[^`]*)`([\s\S]*?)\)\s*;/g;
  let m: RegExpExecArray | null;
  while ((m = patron.exec(texto)) !== null) {
    llamadas.push(m[1] + " ::" + m[2]);
  }
  return llamadas;
}

describe("las llamadas de MolChat llevan sesión", () => {
  it("encuentra las llamadas del contexto", () => {
    // Si el contexto se reescribe y el patrón deja de encajar, la prueba de
    // abajo pasaría en vacío. Este guardarraíl lo impide.
    expect(llamadasAi(fuente).length).toBeGreaterThanOrEqual(6);
  });

  it("ninguna llamada a /ai/ va sin cabecera de autenticación", () => {
    const sinAuth = llamadasAi(fuente).filter(
      (llamada) => !llamada.includes("getAuthHeaders()"),
    );

    expect(sinAuth).toEqual([]);
  });

  it("el chat también la lleva", () => {
    const chat = llamadasAi(fuente).filter((l) => l.startsWith("/ai/chat"));

    expect(chat.length).toBe(1);
    expect(chat[0]).toContain("getAuthHeaders()");
  });

  it("todas las rutas del navegador de modelos llevan la misma sesión", () => {
    const llamadas = llamadasAi(ajustes).filter((l) => l.startsWith("/ai/models"));

    expect(llamadas).toHaveLength(6);
    expect(llamadas.filter((llamada) => !llamada.includes("getAuthHeaders()"))).toEqual([]);
  });
});
