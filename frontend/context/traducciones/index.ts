// =====================================================================
// Traducciones por superficie — un modulo por pantalla
// =====================================================================
//
// POR QUE ESTAN SEPARADAS DEL BLOQUE HISTORICO. `LanguageContext.tsx` ya traia
// 274 pares en linea. Al traducir la interfaz entera aparecen unos 600 mas, y
// meterlos ahi daria un archivo de 2500 lineas donde nadie encuentra nada y
// donde dos personas que traduzcan pantallas distintas chocan en cada commit.
//
// UN MODULO POR SUPERFICIE. Es la unidad en la que se revisa: se abre Batch,
// se lee su modulo entero y se comprueba que las dos columnas dicen lo mismo.
// Repartido por orden alfabetico entre 860 claves, eso es imposible.
//
// EL CONTRATO. Cada modulo exporta `{ es, en }` con EXACTAMENTE las mismas
// claves. `idiomasCompletos.test.ts` lo comprueba sobre el diccionario ya
// fusionado, asi que una clave que falte en `en` no llega a produccion.

import { casos } from "./casos";
import { certificacion } from "./certificacion";
import { comun } from "./comun";
import { evaluacion } from "./evaluacion";
import { legal } from "./legal";
import { lote } from "./lote";
import { moldex } from "./moldex";
import { opciones } from "./opciones";
import { paginas } from "./paginas";
import { pro } from "./pro";

/** Las dos columnas de un modulo. Mismas claves, distinto idioma. */
export interface ModuloDeTraduccion {
  readonly es: Readonly<Record<string, string>>;
  readonly en: Readonly<Record<string, string>>;
}

const MODULOS: readonly ModuloDeTraduccion[] = [
  comun, evaluacion, lote, moldex, casos, legal, certificacion, opciones,
  pro, paginas,
];

/**
 * Funde los modulos en las dos columnas.
 *
 * Una clave repetida entre modulos es un ERROR, no una precedencia: significa
 * que dos pantallas creen ser duenas del mismo texto y una de las dos va a
 * cambiar sin querer cuando alguien edite la otra.
 */
function fundir(idioma: "es" | "en"): Record<string, string> {
  const salida: Record<string, string> = {};
  for (const modulo of MODULOS) {
    for (const [clave, valor] of Object.entries(modulo[idioma])) {
      if (clave in salida) {
        throw new Error(
          `Clave de traduccion duplicada entre modulos: "${clave}". ` +
            "Cada texto pertenece a una sola superficie.",
        );
      }
      salida[clave] = valor;
    }
  }
  return salida;
}

export const TRADUCCIONES_POR_SUPERFICIE = {
  es: fundir("es"),
  en: fundir("en"),
} as const;
