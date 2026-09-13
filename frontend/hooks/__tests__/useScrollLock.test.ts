import { afterEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useScrollLock } from "../useScrollLock";

// ─────────────────────────────────────────────────────────────────────────
// El hook guardaba el overflow COMPUTADO y lo reponia como estilo EN LINEA.
//
// `getComputedStyle(body).overflow` no devuelve «lo que escribio el autor»,
// devuelve el valor resuelto por la cascada. Al cerrar el modal ese valor se
// escribia inline, y un estilo inline gana a cualquier hoja: `app/globals.css`
// declara `body { overflow-x: clip }` a proposito —evita que un elemento ancho
// ensanche la pagina en movil— y abrir un modal UNA vez lo anulaba para el
// resto de la sesion.
//
// Y faltaba compensar la barra: quitarla devuelve su anchura al contenido y la
// pagina salta a la derecha al abrir y a la izquierda al cerrar.
// ─────────────────────────────────────────────────────────────────────────

afterEach(() => {
  document.body.style.overflow = "";
  document.body.style.paddingRight = "";
  document.documentElement.style.overflow = "";
});

describe("useScrollLock", () => {
  it("bloquea body y html mientras esta abierto", () => {
    renderHook(() => useScrollLock(true));
    expect(document.body.style.overflow).toBe("hidden");
    // La propagacion body -> viewport solo vale mientras `html` sea `visible`.
    // Bloquear los dos cuesta lo mismo y no depende de esa condicion.
    expect(document.documentElement.style.overflow).toBe("hidden");
  });

  it("no toca nada cuando esta cerrado", () => {
    renderHook(() => useScrollLock(false));
    expect(document.body.style.overflow).toBe("");
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("repone el estilo EN LINEA que habia, no el computado", () => {
    // Este es el fallo exacto: sin valor inline previo, al cerrar debe quedar
    // vacio —no «visible», ni «clip», ni lo que la cascada resolviera—.
    const { unmount } = renderHook(() => useScrollLock(true));
    unmount();
    expect(document.body.style.overflow).toBe("");
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("respeta un overflow inline que ya existiera", () => {
    document.body.style.overflow = "scroll";
    const { unmount } = renderHook(() => useScrollLock(true));
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("scroll");
  });

  it("no deja padding cuando la medida no es una barra plausible", () => {
    // jsdom no maqueta: `clientWidth` es 0 y la resta da la ventana entera.
    // El hook lo descarta en vez de meter mil pixeles de padding.
    const { unmount } = renderHook(() => useScrollLock(true));
    expect(document.body.style.paddingRight).toBe("");
    unmount();
    expect(document.body.style.paddingRight).toBe("");
  });

  it("compensa la anchura de la barra y la devuelve al cerrar", () => {
    // jsdom deja `clientWidth` en 0, asi que se finge tambien el documento:
    // ventana 1015, documento 1000 -> barra de 15 px.
    const anchoReal = window.innerWidth;
    Object.defineProperty(document.documentElement, "clientWidth", { value: 1000, configurable: true });
    Object.defineProperty(window, "innerWidth", { value: 1015, configurable: true });
    try {
      const { unmount } = renderHook(() => useScrollLock(true));
      expect(document.body.style.paddingRight).toBe("15px");
      unmount();
      expect(document.body.style.paddingRight).toBe("");
    } finally {
      Object.defineProperty(window, "innerWidth", { value: anchoReal, configurable: true });
      Object.defineProperty(document.documentElement, "clientWidth", { value: 0, configurable: true });
    }
  });

  it("suma la barra al padding que el body ya tuviera", () => {
    const anchoReal = window.innerWidth;
    document.body.style.paddingRight = "8px";
    Object.defineProperty(document.documentElement, "clientWidth", { value: 1000, configurable: true });
    Object.defineProperty(window, "innerWidth", { value: 1015, configurable: true });
    try {
      const { unmount } = renderHook(() => useScrollLock(true));
      expect(document.body.style.paddingRight).toBe("23px");
      unmount();
      expect(document.body.style.paddingRight).toBe("8px");
    } finally {
      Object.defineProperty(window, "innerWidth", { value: anchoReal, configurable: true });
      Object.defineProperty(document.documentElement, "clientWidth", { value: 0, configurable: true });
    }
  });

  it("descarta una medida absurda en vez de descolocar la pagina", () => {
    // Con `clientWidth` a 0 la resta da la ventana entera. Ninguna barra de
    // escritorio pasa de ~20 px, asi que eso no es una barra.
    Object.defineProperty(document.documentElement, "clientWidth", { value: 0, configurable: true });
    const { unmount } = renderHook(() => useScrollLock(true));
    expect(document.body.style.paddingRight).toBe("");
    unmount();
  });
});
