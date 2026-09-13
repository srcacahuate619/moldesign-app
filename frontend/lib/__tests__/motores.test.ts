/**
 * ENG-004 — «Próximamente» es una promesa, y las promesas se comprueban.
 *
 * Decidido el 2026-09-01, preparando el primer MVP público. El menú avanzado
 * ofrece siete motores; esta build ejecuta dos. ENG-001 ya impidió que los
 * otros cinco se ofrecieran como disponibles, pero seguían anunciándose con
 * «NO INSTALADO» y «SERVICIO APARTE» —lenguaje de avería para algo que
 * simplemente no está construido todavía.
 *
 * Lo que estas pruebas protegen es la regla, no las cadenas: la etiqueta se
 * deriva de `requiere`, que declara el backend. Si alguien vuelve a escribir
 * una lista de identificadores en la interfaz, o si un motor descargable acaba
 * anunciado como futuro, esto falla.
 */
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

import { BADGE_PROXIMAMENTE, esProximamente, textoProximamente } from "../motores";

const MODAL = path.join(__dirname, "..", "..", "components", "interfaces", "pro", "ProOptionsModal.tsx");

describe("ENG-004 — qué se anuncia como Próximamente", () => {
  it("un servicio externo que esta versión no levanta es Próximamente", () => {
    expect(esProximamente({ requiere: "servicio_externo", disponible: false })).toBe(true);
  });

  it("un binario que el instalador no trae es Próximamente", () => {
    expect(esProximamente({ requiere: "binario_externo", disponible: false })).toBe(true);
  });

  it("un motor DESCARGABLE no es Próximamente aunque no esté disponible", () => {
    // ESMFold sin descargar no esta disponible, pero la aplicacion sabe
    // instalarlo y encenderlo. Llamarlo «proximamente» esconderia una
    // capacidad que si existe, y dejaria al investigador sin la accion.
    expect(esProximamente({ requiere: "descarga_bajo_demanda", disponible: false })).toBe(false);
  });

  it("un motor disponible nunca es Próximamente", () => {
    for (const requiere of ["binario_empaquetado", "binario_externo", "servicio_externo", "descarga_bajo_demanda"]) {
      expect(esProximamente({ requiere, disponible: true })).toBe(false);
    }
  });

  it("el texto dice qué SÍ se puede ejecutar, no sólo qué falta", () => {
    const texto = textoProximamente("DiffDock");
    expect(texto).toContain("DiffDock");
    expect(texto).toContain("AutoDock Vina");
    expect(texto).toContain("ESMFold");
  });
});

describe("ENG-004 — la interfaz no vuelve a inventarse el estado", () => {
  const fuente = fs.readFileSync(MODAL, "utf8");

  it("el modal ya no anuncia averías donde hay trabajo pendiente", () => {
    expect(fuente).not.toContain("NO INSTALADO");
    expect(fuente).not.toContain("SERVICIO APARTE");
  });

  it("el modal decide la etiqueta con el helper, no con una lista propia", () => {
    expect(fuente).toContain("esProximamente");
    expect(fuente).toContain(BADGE_PROXIMAMENTE.length > 0 ? "BADGE_PROXIMAMENTE" : "");
    // Ningun identificador de motor puede aparecer en una comparacion directa
    // para decidir disponibilidad: eso es deducir, y el inventario ya lo dice.
    for (const id of ["qvina2", "diffdock", "colabfold", "esmfold-pro", "esmfold-experimental"]) {
      expect(fuente).not.toContain(`requiere === "${id}"`);
    }
  });

  it("estadoMotor expone `requiere`, que es de donde sale la etiqueta", () => {
    expect(fuente).toContain("requiere: encontrado.requiere");
  });
});
