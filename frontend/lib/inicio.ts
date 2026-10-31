// =====================================================================
// Menú de inicio: la web y la versión que describen las notas
// =====================================================================
//
// Viven aquí y no en `app/page.tsx` porque una página de Next sólo puede exportar la página: cualquier otro
// nombre rompe la comprobación de tipos del build.

/**
 * La web de MolDesign. Decisión del propietario (2026-10-11): `moldesign.amezcua-dev.com`, el mismo dominio que
 * la web declara como canónico (`DOMINIO` en `scripts/build_sitio_publico.py`) y que escribe el cierre de todo
 * vídeo de Molcy (`WEB` en `tools/molcy/scripts/marca/cierre.py`); una prueba exige que los tres coincidan. Todas
 * las llamadas a la acción van a su PORTADA, que existe siempre. Antes fue `molecule-design.amezcua-dev.com` (del
 * 10-04 al 10-11) y, unas horas del 10-11, `moldesignapp.amezcua-dev.com`, por error; antes aún,
 * `moldesign.amezcua-dev.com` con dos rutas, `/novedades` y `/ciencia`, que no existían. `/ciencia/` ya existe en
 * `site/`, pero la app no enlaza a ella hasta que esté publicada y comprobada en línea.
 */
export const SITE = "https://moldesign.amezcua-dev.com/";

/**
 * La versión que describen las notas del inicio. Cuando la versión instalada la alcanza, las notas pasan a
 * «publicada» solas: no depende de que alguien se acuerde de cambiar un texto el día de la publicación.
 */
export const VERSION_DE_LAS_NOTAS = "1.0.4";

/** `1.0.10` frente a `1.0.2`: se compara por números, no por texto. */
export function versionAlcanza(instalada: string, objetivo: string): boolean {
  const a = instalada.split(".").map((n) => Number.parseInt(n, 10) || 0);
  const b = objetivo.split(".").map((n) => Number.parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const x = a[i] ?? 0;
    const y = b[i] ?? 0;
    if (x !== y) return x > y;
  }
  return true;
}
