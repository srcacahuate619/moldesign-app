import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KeepAliveContext } from "../../context/KeepAliveContext";
import { LanguageProvider } from "../../context/LanguageContext";
import { AuthProvider } from "../../lib/auth";
import { ThinkingOrb } from "../ui/ThinkingOrb";
import { PipelineTimeline } from "../interfaces/pro/PipelineTimeline";

/**
 * Las pestañas no se desmontan (keep-alive): una pestaña oculta sigue en el DOM con display:none. Medido en el export el
 * 2026-10-10: con Historial oculto, Inicio gastaba ~35 ms de CPU por segundo en reposo por 8 «estrellas» de framer-motion
 * en bucle infinito (las animaciones CSS se detienen solas con display:none; las de framer-motion no). Y un bucle de
 * `requestAnimationFrame` sólo se pausa con la VENTANA oculta, no con la pestaña.
 */

const RAIZ = resolve(process.cwd());

/** Bucles infinitos de framer-motion en una fuente; ignora los comentarios. */
export function buclesInfinitosDeFramer(fuente: string): number {
  const sinComentarios = fuente.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  return (sinComentarios.match(/\brepeat\s*:\s*(Infinity|Number\.POSITIVE_INFINITY)\b/g) ?? []).length;
}

function fuentes(dir: string): string[] {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre);
    if (["node_modules", "__tests__", ".next", ".next-dev", "out"].includes(nombre)) return [];
    if (statSync(ruta).isDirectory()) return fuentes(ruta);
    return /\.(tsx?|jsx?)$/.test(nombre) ? [ruta] : [];
  });
}

describe("animaciones que no deben correr con la pestaña oculta", () => {
  it("el detector ve los bucles infinitos de framer-motion y no se confunde (autotest)", () => {
    expect(buclesInfinitosDeFramer("transition={{ duration: 2, repeat: Infinity }}")).toBe(1);
    expect(buclesInfinitosDeFramer("transition={{repeat:Infinity, delay: 1}}")).toBe(1);
    expect(buclesInfinitosDeFramer("{ repeat: Number.POSITIVE_INFINITY }")).toBe(1);
    expect(buclesInfinitosDeFramer("{ repeat: 3 }")).toBe(0);
    expect(buclesInfinitosDeFramer("// antes: repeat: Infinity\nconst x = 1;")).toBe(0);
    expect(buclesInfinitosDeFramer("/* repeat: Infinity */ const y = 2;")).toBe(0);
    expect(buclesInfinitosDeFramer("const url = 'https://x'; // repeat: Infinity")).toBe(0);
  });

  it("ninguna página ni componente usa un bucle infinito de framer-motion (decoración en bucle: CSS)", () => {
    const archivos = [...fuentes(join(RAIZ, "app")), ...fuentes(join(RAIZ, "components"))];
    expect(archivos.length).toBeGreaterThan(100);
    const culpables = archivos.filter((ruta) => buclesInfinitosDeFramer(readFileSync(ruta, "utf8")) > 0)
      .map((ruta) => relative(RAIZ, ruta));
    expect(culpables).toEqual([]);
  });
});

describe("los bucles de requestAnimationFrame se pausan con la pestaña oculta", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it.each([true, false])("el orbe «procesando» pide fotogramas sólo si su pestaña está a la vista (activa=%s)", (activa) => {
    const raf = vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => 1);
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
    render(<KeepAliveContext.Provider value={activa}><ThinkingOrb state="processing" /></KeepAliveContext.Provider>);
    expect(raf.mock.calls.length > 0).toBe(activa);
  });

  it.each([true, false])("la línea de tiempo de la evaluación no pide fotogramas nunca: sus anillos son CSS (activa=%s)", (activa) => {
    const raf = vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => 1);
    render(
      <AuthProvider><LanguageProvider>
        <KeepAliveContext.Provider value={activa}><PipelineTimeline stageStates={{ vina: "running" }} /></KeepAliveContext.Provider>
      </LanguageProvider></AuthProvider>,
    );
    expect(raf).not.toHaveBeenCalled();
  });
});
