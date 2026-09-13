import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// =====================================================================
// Doc 71, defecto D1: un `\uXXXX` en TEXTO JSX se imprime literal
// =====================================================================
//
// El informe de la VM lo vio en la pestana de explicabilidad: donde debia decir
// «caracteristicas» aparecia la secuencia de escape entera, con su barra
// invertida y sus cuatro digitos.
//
// La causa no es JSON mal decodificado, como parecía. Es una regla del lenguaje
// que se olvida con facilidad: **las secuencias de escape sólo las interpreta el
// parser dentro de un literal de cadena**. En el texto entre etiquetas JSX no
// hay literal, asi que la secuencia son seis caracteres y se pintan seis.
//
// El error es fácil de reintroducir —copiar y pegar de un JSON, de un `.py`, de
// una traducción— y no lo detecta ni el compilador ni el linter, porque es texto
// perfectamente válido. Por eso hay una prueba y no sólo un arreglo.
//
// Ojo con lo que NO se prohíbe: dentro de comillas la secuencia es correcta y se
// usa a propósito (el mapa de etiquetas ECIF de `ProXaiTab` está lleno de ellas
// y renderiza bien). Se inspecciona sólo lo que queda fuera de las comillas.

const RAIZ = join(__dirname, "..", "..");
// Sólo las carpetas de código fuente. Recorrer la raíz entera arrastraba la
// salida de build y tardaba medio minuto; una prueba lenta es una prueba que
// alguien acaba desactivando.
const CARPETAS = ["components", "app", "lib", "context", "hooks"];
const SEQ = String.fromCharCode(92) + "u"; // la secuencia literal, no un escape

function tsxDe(dir: string): string[] {
  const salida: string[] = [];
  for (const entrada of readdirSync(dir)) {
    if (entrada === "node_modules" || entrada === ".next" || entrada.startsWith(".next-")) continue;
    const ruta = join(dir, entrada);
    if (statSync(ruta).isDirectory()) salida.push(...tsxDe(ruta));
    else if (entrada.endsWith(".tsx")) salida.push(ruta);
  }
  return salida;
}

/** La línea sin el contenido de comillas dobles, simples y plantillas. */
function fueraDeComillas(linea: string): string {
  return linea
    .replace(/"[^"]*"/g, '""')
    .replace(/'[^']*'/g, "''")
    .replace(/`[^`]*`/g, "``");
}

describe("no hay secuencias de escape en texto JSX", () => {
  it("ningun .tsx imprime una secuencia de escape literal al usuario", () => {
    const culpables: string[] = [];
    const archivos = CARPETAS.flatMap((c) => {
      const ruta = join(RAIZ, c);
      try {
        return statSync(ruta).isDirectory() ? tsxDe(ruta) : [];
      } catch {
        return [];
      }
    });
    expect(archivos.length).toBeGreaterThan(20); // el barrido encontró código

    for (const archivo of archivos) {
      const lineas = readFileSync(archivo, "utf8").split("\n");
      lineas.forEach((linea, i) => {
        if (!linea.includes(SEQ)) return;
        if (fueraDeComillas(linea).includes(SEQ)) {
          culpables.push(`${archivo.replace(RAIZ, "")}:${i + 1}  ${linea.trim().slice(0, 100)}`);
        }
      });
    }
    expect(culpables, `se imprimirían literalmente:\n${culpables.join("\n")}`).toEqual([]);
  });
});
