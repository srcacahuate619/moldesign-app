import { describe, expect, it } from "vitest";

import { esExcepcionCruda } from "../receptorNoDisponible";

// Los motivos son los REALES de `GET /targets/` (15 receptores con
// `disponible: false`, medidos el 2026-10-03 sobre la cápsula de QA).
const EXCEPCIONES_REALES = [
  "Meeko no puede construir el receptor (RuntimeError: Expected 2 paddings for (A:50, A:52) with bonds [(10, 11)], but got 0).",
  "Meeko no puede construir el receptor (RuntimeError: Expected 2 paddings for (A:1633, A:1646) with bonds [(9, 9)], but got 0).",
  "Meeko no puede construir el receptor (RuntimeError: for residue_key='A:244', 4 have passed: ['CYS', 'CYX', 'CYX-', 'NCYX'] and tied for fewest missing and excess H: CYX C",
  "Meeko no puede construir el receptor (RuntimeError: Expected 2 paddings for (B:3, B:51) with bonds [(9, 9)], but got 1).",
  "Meeko no puede construir el receptor (RuntimeError: for residue_key='A:43', 3 have passed: ['HIE', 'HID', 'HIP'] and tied for fewest missing and excess H: HIE HID ).",
  "Meeko no puede construir el receptor (RuntimeError: for residue_key='A:383', 3 have passed: ['HIE', 'HID', 'HIP'] and tied for fewest missing and excess H: HIE HID ).",
];

// Estas ya son frases redactadas: se enseñan tal cual.
const FRASES_REDACTADAS = [
  "Meeko elimina 7 residuo(s) a 6 Å o menos de la caja, del sitio: GLY A24 (3.027 Å), GLY A25 (2.577 Å). No se acopla contra un sitio incompleto.",
  "Meeko elimina 1 residuo(s) a 6 Å o menos de la caja, del sitio: GLU A55 (0.941 Å). No se acopla contra un sitio incompleto.",
  "Meeko elimina 1 residuo(s) a 6 Å o menos de la caja, del sitio: DC P10 (0.0 Å). No se acopla contra un sitio incompleto.",
];

describe("esExcepcionCruda (QA1-003)", () => {
  it.each(EXCEPCIONES_REALES)("reconoce la excepción cruda: %s", (motivo) => {
    expect(esExcepcionCruda(motivo)).toBe(true);
  });

  it.each(FRASES_REDACTADAS)("deja pasar la frase redactada: %s", (motivo) => {
    expect(esExcepcionCruda(motivo)).toBe(false);
  });

  it("reconoce un Traceback y otros errores con nombre", () => {
    expect(esExcepcionCruda("Traceback (most recent call last):\n  File x")).toBe(true);
    expect(esExcepcionCruda("ValueError: no se pudo")).toBe(true);
  });

  it("no inventa una excepción donde no la hay", () => {
    expect(esExcepcionCruda(null)).toBe(false);
    expect(esExcepcionCruda(undefined)).toBe(false);
    expect(esExcepcionCruda("")).toBe(false);
    expect(esExcepcionCruda("El receptor no está disponible por una decisión de curación.")).toBe(false);
  });
});
