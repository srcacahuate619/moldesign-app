// =====================================================================
// Los controles físicos, dichos en el idioma de la interfaz
// =====================================================================
//
// EL FALLO QUE ARREGLA. `checks_que_fallan` viaja con los nombres de columna
// que devuelve PoseBusters —`minimum_distance_to_protein`,
// `internal_steric_clash`, `non-aromatic_ring_non-flatness`— y la pestaña
// «Evidencia estructural» los imprimía tal cual. En una pantalla íntegramente
// en español, la línea que decide si una pose sirve o no estaba escrita en
// inglés y en jerga de identificador.
//
// LO QUE NO CAMBIA. El código canónico sigue viajando en el resultado, en el
// dossier y en el `title` de cada control en pantalla: es lo que permite
// reproducir el control contra la misma versión de PoseBusters. Traducir la
// etiqueta y perder el identificador habría cambiado un problema por otro peor.
//
// Un control que no esté en el diccionario se enseña con su código. Es feo a
// propósito: así una versión nueva de PoseBusters con un control nuevo se ve
// —y se puede traducir— en vez de desaparecer de la lista.

/** La firma de `t` que expone `LanguageContext`. */
type Traductor = (clave: string) => string;

export function nombreDeControl(t: Traductor, codigo: string): string {
  const clave = `se_check_${codigo}`;
  const texto = t(clave);
  return texto === clave ? codigo : texto;
}
