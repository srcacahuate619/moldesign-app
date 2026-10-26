/**
 * Qué puede elegir el investigador en el menú de motores.
 *
 * Decisión del propietario (2026-10-07): un motor que esta versión no ejecuta no se lista.
 * Antes se anunciaba como «Próximamente» (ENG-004). Lo que queda: el backend declara los
 * motores con su motivo (ENG-001, `test_motores_declarados_son_los_que_existen.py`); el menú
 * ofrece sólo lo que se puede elegir, y ESMFold se puede elegir aunque esté apagado.
 */
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

import { puedeElegirse } from "../motores";

const MODAL = path.join(__dirname, "..", "..", "components", "interfaces", "pro", "ProOptionsModal.tsx");

describe("puedeElegirse — qué se ofrece en el menú", () => {
  it("un motor que ya responde se puede elegir", () => {
    expect(puedeElegirse({ disponible: true, accion: null })).toBe(true);
  });

  it("un motor instalado y apagado se puede elegir: la corrida lo enciende al empezar", () => {
    expect(puedeElegirse({ disponible: false, accion: "encender" })).toBe(true);
  });

  it("un motor sin descargar no se puede elegir todavía", () => {
    expect(puedeElegirse({ disponible: false, accion: "descargar" })).toBe(false);
  });

  it("un motor con un arranque fallido no se puede elegir hasta reintentarlo", () => {
    expect(puedeElegirse({ disponible: false, accion: "reintentar" })).toBe(false);
  });

  it("un motor al que le falta una librería no se puede elegir", () => {
    expect(puedeElegirse({ disponible: false, accion: null })).toBe(false);
  });
});

describe("el menú no lista motores que esta versión no ejecuta", () => {
  const fuente = fs.readFileSync(MODAL, "utf8");

  it("no hay opciones para QuickVina, DiffDock, ColabFold, ESMFold Pro ni RFdiffusion", () => {
    for (const id of ["qvina2", "diffdock", "colabfold", "esmfold-pro", "esmfold-experimental"]) {
      expect(fuente).not.toContain(`"${id}"`);
    }
  });

  it("y ya no se anuncian como Próximamente", () => {
    expect(fuente).not.toContain("esProximamente");
    expect(fuente).not.toContain("BADGE_PROXIMAMENTE");
  });

  it("el modal sigue consultando el inventario del backend", () => {
    expect(fuente).toContain("inventarioDeMotores");
  });
});

describe("ESMFold no depende de la molécula ni se enciende con un botón", () => {
  const fuente = fs.readFileSync(MODAL, "utf8");

  it("no hay «auto-detecta» ni decisión por molécula en el modal", () => {
    expect(fuente).not.toContain("auto_a7ff1c2aeb72");
    expect(fuente).not.toContain("isPeptide");
  });

  it("no hay un botón «Encender» de primer nivel", () => {
    expect(fuente).not.toContain('t("pr_cfg_encender")');
  });
});
