// =====================================================================
// Guardia: una magnitud ausente no puede tumbar una pestaña
// =====================================================================
//
// La pestaña Propiedades reventaba con `Cannot read properties of null
// (reading 'toFixed')` porque la guarda era `!== undefined` y el backend manda
// `null`. Cuatro llamadas en el mismo archivo lo hacían mal y siete lo hacían
// bien: no había ninguna prueba que distinguiera unas de otras.
//
// El caso que importa es `null`, y por eso va primero.

import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

import { hayNumero, numeroOGuion, SIN_DATO } from "../formatoNumerico";

describe("numeroOGuion", () => {
  it("devuelve el guion con null — el caso que rompía la pestaña", () => {
    expect(numeroOGuion(null, 2)).toBe(SIN_DATO);
  });

  it("devuelve el guion con undefined", () => {
    expect(numeroOGuion(undefined, 2)).toBe(SIN_DATO);
  });

  it("devuelve el guion con NaN e Infinity, que un cálculo fallido sí produce", () => {
    expect(numeroOGuion(Number.NaN, 2)).toBe(SIN_DATO);
    expect(numeroOGuion(Number.POSITIVE_INFINITY, 2)).toBe(SIN_DATO);
  });

  it("formatea un número normal con su sufijo", () => {
    expect(numeroOGuion(342.1234, 1, " g/mol")).toBe("342.1 g/mol");
  });

  it("el CERO es un valor, no una ausencia", () => {
    // Un `if (valor)` lo trataria como ausente y borraria un dato real.
    expect(numeroOGuion(0, 2)).toBe("0.00");
    expect(numeroOGuion(0, 0, " / 100")).toBe("0 / 100");
  });

  it("no acepta una cadena numérica: un JSON mal tipado no debe colarse", () => {
    expect(numeroOGuion("3.14" as unknown, 2)).toBe(SIN_DATO);
  });
});

describe("hayNumero", () => {
  it("distingue el cero de la ausencia", () => {
    expect(hayNumero(0)).toBe(true);
    expect(hayNumero(null)).toBe(false);
    expect(hayNumero(undefined)).toBe(false);
    expect(hayNumero(Number.NaN)).toBe(false);
  });
});

describe("la pestaña Propiedades no vuelve al patrón roto", () => {
  it("ningún `!== undefined` seguido de toFixed en ProParametersTab", () => {
    // `null !== undefined` es true, asi que esa guarda deja pasar el null y
    // `.toFixed()` explota. Es un test estatico a proposito: cubre las lineas
    // que alguien anada manana, no solo las que hoy se ejercitan.
    const archivo = path.join(
      __dirname, "..", "..", "components", "interfaces", "pro", "ProParametersTab.tsx",
    );
    const fuente = fs.readFileSync(archivo, "utf8");
    expect(fuente).not.toMatch(/!==\s*undefined[^\n]*\.toFixed\(/);
  });
});
