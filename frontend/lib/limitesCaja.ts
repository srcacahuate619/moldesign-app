/**
 * Límites de la caja de búsqueda que el backend EJECUTA.
 *
 * Espejo de `services/docking/preflight.py` (`CAJA_LADO_MIN_A`,
 * `CAJA_LADO_MAX_A`, `CAJA_CENTRO_MAX_A`); `limitesCaja.test.ts` lee ese archivo
 * y falla si los números dejan de coincidir.
 *
 * SOL-13. La interfaz limitaba el centro a ±100 Å y el lado a 50 Å, y recortaba
 * en silencio lo que se tecleara fuera de ahí, mientras el backend admite
 * centros finitos hasta ±10000 Å y lados de 5 a 80 Å. El origen de coordenadas
 * lo fija la estructura —no hay un «dentro del receptor» universal—, así que un
 * tope más estrecho que el de ejecución desplaza la búsqueda sin que nadie lo
 * decida. El volumen excesivo ya se advierte aparte (`search_policy`).
 */
export const CAJA_CENTRO_MAX_A = 10000;
export const CAJA_LADO_MIN_A = 5;
export const CAJA_LADO_MAX_A = 80;
