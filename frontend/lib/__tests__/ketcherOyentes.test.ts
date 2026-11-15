/**
 * Los oyentes que Ketcher 3.18.0 deja en `window` y `document` se retiran al desmontar el editor, y los de nadie más.
 *
 * Ketcher se imita registrando lo mismo, en el mismo orden y desde el mismo tipo de función que su `initApp` y su
 * `domEventSetup` (ver `lib/ketcherOyentes.ts`). Lo que se mira es si un evento sigue llegando a quien no debe.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { estadoDeLaVigilancia, olvidarServicioDeAjustes, vigilarKetcher } from "../ketcherOyentes";

type Suscripcion = { handlers: Array<{ f: (e: Event) => void }>; dispatch: (e: Event) => void };

function suscripcion(): Suscripcion {
  return {
    handlers: [],
    dispatch(e: Event) { for (const h of this.handlers) h.f(e); },
  };
}

/** Un editor de mentira que se monta como el de Ketcher. Devuelve lo que recibe cada evento global. */
function arrancarKetcher(raiz: HTMLElement) {
  const recibido = { resize: 0, mousemove: 0, mouseup: 0, mouseleave: 0 };
  const editor = { event: {} as Record<string, Suscripcion> };
  // initApp: teclado en su raíz y, en la misma tarea, `resize` en la ventana. Ketcher lo escribe sin calificar
  // (`addEventListener(...)`), que en el navegador es la ventana; en jsdom la ventana y el objeto global son dos.
  raiz.addEventListener("keydown", () => {});
  window.addEventListener("resize", () => { recibido.resize++; });
  // domEventSetup: una función anónima por evento, que reparte a `editor.event[evento]`.
  for (const evento of ["mousemove", "mouseup", "mouseleave"] as const) {
    const subs = suscripcion();
    editor.event[evento] = subs;
    subs.handlers.push({ f: () => { recibido[evento]++; } });
    // El texto de esta función es lo que reconoce el vigía: es el de Ketcher.
    document.addEventListener(evento, function (this: unknown, ...args: unknown[]) {
      if ((window as { isPolymerEditorTurnedOn?: boolean }).isPolymerEditorTurnedOn) return;
      subs.dispatch.apply(subs, args as [Event]);
    });
  }
  return { recibido, editor };
}

const disparar = () => {
  window.dispatchEvent(new Event("resize"));
  for (const e of ["mousemove", "mouseup", "mouseleave"]) document.dispatchEvent(new Event(e));
};
const raiz = () => { const r = document.createElement("div"); r.className = "Ketcher-root"; document.body.appendChild(r); return r; };

beforeEach(() => { document.body.innerHTML = ""; });
// Los espías se retiran entre pruebas: uno que se queda puesto sigue contando en la siguiente.
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("los oyentes de Ketcher", () => {
  it("sin vigilar, siguen recibiendo eventos con el editor ya desmontado (el fallo)", async () => {
    const r = raiz();
    await Promise.resolve();
    const { recibido } = arrancarKetcher(r);
    r.remove();
    disparar();
    expect(recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
  });

  it("vigilado, al desmontar dejan de recibir", async () => {
    const r = raiz();
    const vigia = vigilarKetcher(r);
    await Promise.resolve(); // Ketcher arranca después de una espera
    const { recibido, editor } = arrancarKetcher(r);
    vigia.listo(editor);
    disparar();
    expect(recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    r.remove();
    vigia.soltar();
    disparar();
    expect(recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 0, documentoEnvuelto: false });
  });

  it("no toca los oyentes de nadie más, aunque se registren en el mismo momento", async () => {
    const r = raiz();
    const vigia = vigilarKetcher(r);
    const ajenos = { resize: 0, mousemove: 0 };
    window.addEventListener("resize", () => { ajenos.resize++; }); // el visor 3D, antes que Ketcher
    document.addEventListener("mousemove", () => { ajenos.mousemove++; });
    await Promise.resolve();
    const { editor } = arrancarKetcher(r);
    window.addEventListener("resize", () => { ajenos.resize++; }); // y otro después
    vigia.listo(editor);
    r.remove();
    vigia.soltar();
    disparar();
    expect(ajenos).toEqual({ resize: 2, mousemove: 1 });
  });

  it("si se desmonta mientras arranca, limpia cuando Ketcher termina", async () => {
    const r = raiz();
    const vigia = vigilarKetcher(r);
    r.remove();
    vigia.soltar();
    await Promise.resolve();
    const { recibido, editor } = arrancarKetcher(r);
    vigia.listo(editor);
    disparar();
    expect(recibido).toEqual({ resize: 0, mousemove: 0, mouseup: 0, mouseleave: 0 });
  });

  it("si Ketcher nunca termina de arrancar, la página no se queda vigilada para siempre", async () => {
    vi.useFakeTimers();
    const r = raiz();
    const vigia = vigilarKetcher(r);
    r.remove();
    vigia.soltar();
    // Llegó a registrar el teclado y no avisó nunca.
    r.addEventListener("keydown", () => {});
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 1, documentoEnvuelto: true });
    expect(Object.prototype.hasOwnProperty.call(r, "addEventListener")).toBe(true);
    vi.advanceTimersByTime(30_000);
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 0, documentoEnvuelto: false });
    expect(Object.prototype.hasOwnProperty.call(r, "addEventListener")).toBe(false);
  });

  it("modo estricto: Ketcher sustituye su instancia en la misma raíz y la primera también se limpia", async () => {
    olvidarServicioDeAjustes();
    const r = raiz();
    const vigia = vigilarKetcher(r);
    await Promise.resolve();
    const primero = arrancarKetcher(r);
    vigia.listo(primero.editor);
    // React desmonta y vuelve a montar el editor; Ketcher destruye la primera instancia y arranca otra en la misma raíz.
    await Promise.resolve();
    const segundo = arrancarKetcher(r);
    vigia.listo(segundo.editor);
    disparar();
    expect(primero.recibido).toEqual({ resize: 0, mousemove: 0, mouseup: 0, mouseleave: 0 });
    expect(segundo.recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    r.remove();
    vigia.soltar();
    disparar();
    expect(segundo.recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 0, documentoEnvuelto: false });
  });

  it("la herramienta del editor central se da de baja de los conjuntos estáticos de RotationView", async () => {
    // Imita `RotationView`: dos conjuntos de la clase, no de la instancia, que sobreviven a todos los editores.
    const rotacion = { asa: new Set<() => void>(), centro: new Set<() => void>() };
    const crearCentral = (micro: unknown) => {
      const herramienta = { asa: () => {}, centro: () => {} } as Record<string, unknown>;
      rotacion.asa.add(herramienta.asa as () => void);
      rotacion.centro.add(herramienta.centro as () => void);
      herramienta.rotationHandleUnsubscribe = () => rotacion.asa.delete(herramienta.asa as () => void);
      herramienta.rotationCenterUnsubscribe = () => rotacion.centro.delete(herramienta.centro as () => void);
      return { micromoleculesEditor: micro, tool: herramienta, destroy: vi.fn(() => { if (vigente === central) vigente = undefined; }) };
    };
    let vigente: unknown;
    let central: ReturnType<typeof crearCentral> | undefined;

    const r1 = raiz();
    const v1 = vigilarKetcher(r1, { editorCentral: () => vigente });
    await Promise.resolve();
    const k1 = arrancarKetcher(r1);
    const c1 = central = crearCentral(k1.editor);
    vigente = c1;
    v1.listo(k1.editor);
    expect(rotacion.asa.size).toBe(1);

    // Cambio de caso: el editor nuevo arranca DESPUÉS de soltar el viejo, como en la aplicación.
    r1.remove();
    v1.soltar();
    expect(rotacion).toEqual({ asa: new Set(), centro: new Set() });
    expect(c1.destroy).toHaveBeenCalledTimes(1);

    const r2 = raiz();
    const v2 = vigilarKetcher(r2, { editorCentral: () => vigente });
    await Promise.resolve();
    const k2 = arrancarKetcher(r2);
    const c2 = central = crearCentral(k2.editor);
    vigente = c2;
    v2.listo(k2.editor);
    expect(rotacion.asa.size).toBe(1);
    expect(vigente).toBe(c2);
  });

  it("cada Ketcher retira su oyente del servicio de ajustes, que es uno para toda la página", async () => {
    olvidarServicioDeAjustes();
    // Imita el `EventEmitter` del servicio: el constructor de cada Ketcher se suscribe y no guarda cómo darse de baja.
    const oyentes: Array<(...a: unknown[]) => void> = [];
    const servicio = { emitter: {
      listeners: (evento: string) => (evento === "settings:changed" ? [...oyentes] : []),
      off: (_evento: string, f: (...a: unknown[]) => void) => { const i = oyentes.indexOf(f); if (i >= 0) oyentes.splice(i, 1); },
    } };
    const montarUno = async () => {
      const r = raiz();
      const v = vigilarKetcher(r);
      await Promise.resolve();
      const k = arrancarKetcher(r);
      const ketcher = { settingsService: servicio };
      const suyo = () => { void ketcher; };
      oyentes.push(suyo);
      v.listo(k.editor, ketcher);
      return { r, v, suyo };
    };
    // El primero de la página (otra pestaña, por ejemplo) sigue vivo todo el rato.
    const vivo = await montarUno();
    for (let i = 0; i < 3; i++) {
      const caso = await montarUno();
      expect(oyentes).toEqual([vivo.suyo, caso.suyo]);
      caso.r.remove();
      caso.v.soltar();
      expect(oyentes).toEqual([vivo.suyo]);
    }
    vivo.r.remove();
    vivo.v.soltar();
    expect(oyentes).toEqual([]);
  });

  it("con dos editores arrancando a la vez no retira ningún oyente de ajustes: no sabe de quién es", async () => {
    olvidarServicioDeAjustes();
    const oyentes: unknown[] = [];
    const servicio = { emitter: { listeners: () => [...oyentes], off: vi.fn() } };
    const r1 = raiz(), r2 = raiz();
    const v1 = vigilarKetcher(r1);
    const v2 = vigilarKetcher(r2);
    await Promise.resolve();
    const k1 = arrancarKetcher(r1);
    oyentes.push(() => {});
    const k2 = arrancarKetcher(r2);
    oyentes.push(() => {});
    v1.listo(k1.editor, { settingsService: servicio });
    v2.listo(k2.editor, { settingsService: servicio });
    r1.remove();
    v1.soltar();
    expect(servicio.emitter.off).not.toHaveBeenCalled();
  });

  it("no destruye el editor central si ya es el de otro editor vivo", async () => {
    const r1 = raiz();
    let vigente: unknown;
    const v1 = vigilarKetcher(r1, { editorCentral: () => vigente });
    await Promise.resolve();
    const k1 = arrancarKetcher(r1);
    const darDeBaja = vi.fn();
    const c1 = { micromoleculesEditor: k1.editor, tool: { rotationCenterUnsubscribe: darDeBaja }, destroy: vi.fn() };
    vigente = c1;
    v1.listo(k1.editor);
    // Otro Ketcher (otra pestaña) crea el suyo antes de que éste se desmonte.
    const c2 = { micromoleculesEditor: {}, destroy: vi.fn() };
    vigente = c2;
    r1.remove();
    v1.soltar();
    expect(darDeBaja).toHaveBeenCalledTimes(1);
    expect(c1.destroy).not.toHaveBeenCalled();
    expect(c2.destroy).not.toHaveBeenCalled();
  });

  it("con dos editores arrancando a la vez no se atribuye nada, pero el del muerto se retira al primer evento", async () => {
    const r1 = raiz(), r2 = raiz();
    const v1 = vigilarKetcher(r1);
    const v2 = vigilarKetcher(r2);
    await Promise.resolve();
    const k1 = arrancarKetcher(r1);
    const k2 = arrancarKetcher(r2);
    v1.listo(k1.editor);
    v2.listo(k2.editor);
    r1.remove();
    v1.soltar();
    disparar();
    disparar();
    // El vivo sigue recibiendo; el muerto no, y su oyente ya no está.
    expect(k2.recibido.mousemove).toBe(2);
    expect(k1.recibido.mousemove).toBe(0);
    const quitar = vi.spyOn(document, "removeEventListener");
    disparar();
    expect(quitar).not.toHaveBeenCalled();
  });
});

/**
 * El modo estricto de React (desarrollo), en el orden en que ocurre de verdad (medido el 2026-11-11 en `next dev`).
 *
 * Ketcher arranca dos veces en la misma raíz, y su aviso público (`onInit`) no sale cuando una instancia termina de
 * arrancar: lo lanza un efecto de su componente exterior, cuando también está listo el editor de macromoléculas. Por eso
 * el aviso de la PRIMERA instancia, ya destruida, llega cuando la segunda ha registrado el teclado y todavía no ha creado
 * su editor.
 */
describe("el modo estricto, en su orden real", () => {
  /** `initApp` de Ketcher: teclado en su raíz y `resize` en la ventana. Devuelve cómo crear después su `Editor`. */
  function empezarKetcher(r: HTMLElement) {
    const recibido = { resize: 0, mousemove: 0, mouseup: 0, mouseleave: 0 };
    r.addEventListener("keydown", () => {});
    window.addEventListener("resize", () => { recibido.resize++; });
    const crearEditor = () => {
      // El lienzo del editor vive dentro de la raíz mientras su instancia existe.
      const lienzo = document.createElement("div");
      r.appendChild(lienzo);
      const editor = { event: {} as Record<string, Suscripcion>, render: { clientArea: lienzo } };
      for (const evento of ["mousemove", "mouseup", "mouseleave"] as const) {
        const subs = suscripcion();
        editor.event[evento] = subs;
        subs.handlers.push({ f: () => { recibido[evento]++; } });
        document.addEventListener(evento, function (this: unknown, ...args: unknown[]) {
          if ((window as { isPolymerEditorTurnedOn?: boolean }).isPolymerEditorTurnedOn) return;
          subs.dispatch.apply(subs, args as [Event]);
        });
      }
      return { editor, lienzo };
    };
    return { recibido, crearEditor };
  }

  it("el aviso tardío de la instancia sustituida no cierra la vigilancia: los oyentes de la que se queda también se retiran", async () => {
    olvidarServicioDeAjustes();
    const r = raiz();
    const vigia = vigilarKetcher(r);
    await Promise.resolve();
    // Primera instancia: arranca entera.
    const primera = empezarKetcher(r);
    const uno = primera.crearEditor();
    // React desmonta y vuelve a montar: Ketcher destruye la primera (su lienzo sale de la raíz) y empieza la segunda.
    uno.lienzo.remove();
    const segunda = empezarKetcher(r);
    // Ahora llega el aviso de la primera, antes de que la segunda cree su editor.
    vigia.listo(uno.editor);
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 1, documentoEnvuelto: true });
    const dos = segunda.crearEditor();
    vigia.listo(dos.editor);
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 0, documentoEnvuelto: false });

    disparar();
    expect(segunda.recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    // El editor muerto deja de atender al ratón en cuanto se sabe que lo está.
    expect(primera.recibido).toMatchObject({ mousemove: 0, mouseup: 0, mouseleave: 0 });

    r.remove();
    vigia.soltar();
    disparar();
    disparar();
    // Nada de ninguna de las dos instancias sigue recibiendo: es lo que retenía la pantalla del caso.
    expect(segunda.recibido).toEqual({ resize: 1, mousemove: 1, mouseup: 1, mouseleave: 1 });
    expect(primera.recibido).toEqual({ resize: 1, mousemove: 0, mouseup: 0, mouseleave: 0 });
    const quitar = vi.spyOn(document, "removeEventListener");
    disparar();
    expect(quitar).not.toHaveBeenCalled();
    quitar.mockRestore();
  });

  it("un aviso con el lienzo fuera de la raíz sí cierra si el editor ya se desmontó de verdad", async () => {
    const r = raiz();
    const vigia = vigilarKetcher(r);
    await Promise.resolve();
    const k = empezarKetcher(r);
    const uno = k.crearEditor();
    // Cambio de caso mientras arrancaba: la raíz se vacía y el aviso llega después.
    r.remove();
    uno.lienzo.remove();
    vigia.soltar();
    vigia.listo(uno.editor);
    disparar();
    expect(k.recibido).toEqual({ resize: 0, mousemove: 0, mouseup: 0, mouseleave: 0 });
    expect(estadoDeLaVigilancia()).toEqual({ arrancando: 0, documentoEnvuelto: false });
  });

  /** La pantalla como la monta Ketcher: dos cajas hermanas, la del editor de moléculas y la del de macromoléculas. */
  function pantallaDeKetcher() {
    const marco = document.createElement("div");
    const cajaMicro = document.createElement("div");
    const cajaMacro = document.createElement("div");
    cajaMicro.setAttribute("data-ketcher-editor", "true");
    cajaMacro.setAttribute("data-ketcher-editor", "true");
    const r = document.createElement("div");
    r.className = "Ketcher-root";
    const raizMacro = document.createElement("div");
    raizMacro.className = "Ketcher-polymer-editor-root";
    cajaMicro.appendChild(r);
    cajaMacro.appendChild(raizMacro);
    marco.append(cajaMacro, cajaMicro);
    document.body.appendChild(marco);
    return { marco, r, raizMacro };
  }

  it("el editor central se reconoce por dónde está su raíz cuando Ketcher lo creó sin editor de moléculas", async () => {
    // En modo estricto `new CoreEditor()` toma «el último Ketcher añadido», que aún no tiene editor: se queda con null.
    const { marco, r, raizMacro } = pantallaDeKetcher();
    const darDeBaja = vi.fn();
    const central = { micromoleculesEditor: null, ketcherRootElement: raizMacro, tool: { rotationCenterUnsubscribe: darDeBaja, rotationHandleUnsubscribe: darDeBaja }, destroy: vi.fn() };
    const vigia = vigilarKetcher(r, { editorCentral: () => central });
    await Promise.resolve();
    const k = empezarKetcher(r);
    const uno = k.crearEditor();
    vigia.listo(uno.editor);
    marco.remove();
    vigia.soltar();
    expect(darDeBaja).toHaveBeenCalledTimes(2);
    expect(central.destroy).toHaveBeenCalledTimes(1);
  });

  it("no toca un editor central cuya raíz está en otra pantalla", async () => {
    const { marco, r } = pantallaDeKetcher();
    const otra = pantallaDeKetcher();
    const darDeBaja = vi.fn();
    const ajeno = { micromoleculesEditor: null, ketcherRootElement: otra.raizMacro, tool: { rotationCenterUnsubscribe: darDeBaja }, destroy: vi.fn() };
    const vigia = vigilarKetcher(r, { editorCentral: () => ajeno });
    await Promise.resolve();
    const k = empezarKetcher(r);
    vigia.listo(k.crearEditor().editor);
    marco.remove();
    vigia.soltar();
    expect(darDeBaja).not.toHaveBeenCalled();
    expect(ajeno.destroy).not.toHaveBeenCalled();
  });
});
