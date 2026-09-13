import { describe, expect, it } from "vitest";
import {
  cuentaQueImporta,
  normalizarAviso,
  normalizarAvisos,
  ordenarPorSeveridad,
  type AvisoDeclarado,
} from "../avisos";

// ─────────────────────────────────────────────────────────────────────────
// La severidad la declara quien emite el aviso.
//
// `ProAlertsTab` la deducia buscando subcadenas. Sobre los 184 literales de
// aviso que emite hoy el backend esa regla no producia ningun falso verde,
// pero metia el 86 % en la misma «nota cientifica»: alli acababan
// «MOTOR SUSTITUIDO», «afinidad debil» y «la semilla no coincide».
//
// El generador del PDF tenia la misma estructura con `"sin"` en su lista de
// positivos, y ahi si disparaba: «Vina no encontrado. Devolviendo estructura
// plegada sin docking» salia como [POSITIVA], en verde, en el documento que se
// firma.
// ─────────────────────────────────────────────────────────────────────────

describe("normalizacion de avisos", () => {
  it("acepta el aviso nuevo con su severidad declarada", () => {
    expect(
      normalizarAviso({ codigo: "MOTOR_SUSTITUIDO", severidad: "critica", mensaje: "x" }),
    ).toEqual({ codigo: "MOTOR_SUSTITUIDO", severidad: "critica", mensaje: "x" });
  });

  it("una cadena heredada NO se convierte en info", () => {
    // `heredada` significa «no se declaro». `info` significa «no importa».
    // Convertir la primera en la segunda seria volver a decidirlo nosotros.
    const aviso = normalizarAviso("Las afinidades se extrajeron del stdout.");
    expect(aviso?.severidad).toBe("heredada");
    expect(aviso?.codigo).toBe("HEREDADO");
  });

  it.each([
    "Vina no encontrado. Devolviendo estructura plegada sin docking.",
    "conformación 3 sin minimizar (MMFF no disponible)",
    "Estructura APO (sin ligando): se usó MolPocket para detectar el pocket.",
    "No cumple la regla de Lipinski (MW > 500).",
    "No es seguro para administración oral.",
    "No se detectó toxicidad.",
  ])("ninguna redaccion fabrica una severidad: %s", (texto) => {
    expect(normalizarAviso(texto)?.severidad).toBe("heredada");
  });

  it("rechaza una severidad inventada", () => {
    expect(
      normalizarAviso({ codigo: "X", severidad: "muy_grave", mensaje: "y" })?.severidad,
    ).toBe("heredada");
  });

  it("descarta los huecos en vez de imprimirlos", () => {
    expect(normalizarAvisos(["", "  ", null, undefined, { mensaje: "" }])).toEqual([]);
  });

  it("normaliza una lista mezclada de corrida nueva y heredada", () => {
    const salida = normalizarAvisos([
      "aviso viejo",
      { codigo: "AFINIDAD_DEBIL", severidad: "precaucion", mensaje: "debil" },
    ]);
    expect(salida.map((a) => a.severidad)).toEqual(["heredada", "precaucion"]);
  });

  it("no explota si el backend manda algo que no es una lista", () => {
    expect(normalizarAvisos(null)).toEqual([]);
    expect(normalizarAvisos("una cadena suelta")).toEqual([]);
  });
});

describe("orden de lectura", () => {
  const avisos: AvisoDeclarado[] = [
    { codigo: "A", severidad: "info", mensaje: "procedencia del parseo" },
    { codigo: "B", severidad: "positiva", mensaje: "eficiencia excepcional" },
    { codigo: "C", severidad: "critica", mensaje: "motor sustituido" },
    { codigo: "D", severidad: "heredada", mensaje: "aviso viejo" },
    { codigo: "E", severidad: "precaucion", mensaje: "afinidad debil" },
  ];

  it("lo que invalida va primero", () => {
    // Antes el orden era el de emision: un «MOTOR SUSTITUIDO» podia quedar
    // sexto de ocho, debajo de tres notas de procedencia.
    expect(ordenarPorSeveridad(avisos).map((a) => a.codigo)).toEqual([
      "C", "E", "D", "A", "B",
    ]);
  });

  it("no muta la lista original", () => {
    const copia = [...avisos];
    ordenarPorSeveridad(avisos);
    expect(avisos).toEqual(copia);
  });
});

describe("el numero del badge", () => {
  it("cuenta lo que exige atencion, no todo lo que hay", () => {
    // Cinco notas de procedencia enseñaban un «5» tan llamativo como cinco
    // fallos reales.
    const avisos = normalizarAvisos([
      { codigo: "A", severidad: "info", mensaje: "a" },
      { codigo: "B", severidad: "info", mensaje: "b" },
      { codigo: "C", severidad: "critica", mensaje: "c" },
      { codigo: "D", severidad: "precaucion", mensaje: "d" },
      { codigo: "E", severidad: "positiva", mensaje: "e" },
    ]);
    expect(avisos).toHaveLength(5);
    expect(cuentaQueImporta(avisos)).toBe(2);
  });

  it("una corrida heredada no infla el contador", () => {
    // No se sabe su severidad; contarla como alerta seria inventarla.
    expect(cuentaQueImporta(normalizarAvisos(["viejo", "otro viejo"]))).toBe(0);
  });
});
