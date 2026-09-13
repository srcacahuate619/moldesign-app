# Gate runtime de Batch — APROBADO

**Fecha:** 2026-08-30  
**Estado:** 🟢 aprobado para el alcance de cierre vertical  
**Ejecutor reproducible:** `scripts/accept_batch_runtime.py`

## Resultado

La pestaña Batch/Cohortes completó una corrida real con AutoDock Vina y Meeko
empaquetados, persistió cohorte, configuración, filas, evidencia y dossier,
reinició el backend sobre la misma SQLite y recuperó la última corrida desde el
backend sin depender de `localStorage`.

Evidencia aceptada:

- directorio: `tmp/batch-runtime-20260830T182915Z/`;
- cohorte: `ea633f44-bb61-45a9-882b-75d773cccb60`;
- corrida: `bf26dbfc-5e69-4349-9ca8-5a3d1cf4d31e`;
- afinidad Vina observada: `-5.867 kcal/mol`;
- filas: una `completed` y una `duplicate_reused`;
- semilla solicitada, efectiva, observada por Vina y archivada en el protocolo: `73`;
- segunda cuenta rechazada en seis superficies privadas con `404`;
- PDF y ZIP verificable generados; ZIP con manifiesto y receptor preparado.

## Fallos descubiertos y corregidos por el gate

1. La semilla declarada por Batch no llegaba a Vina. Ahora forma parte de los
   parámetros reales, del fingerprint y del protocolo persistido.
2. La deduplicación de moléculas ignoraba al propietario. Ahora se deduplica por
   usuario, receptor y ligando; dos investigadores no comparten la misma fila.
3. Batch exigía un PDBQT previo sin ofrecer cómo producirlo. La apertura prepara
   el receptor una vez, antes del primer `INSERT`, y congela su SHA-256; un fallo
   de Meeko deja cero corridas parciales.
4. Abrir una cohorte guardada no restauraba cadena, motor, exhaustividad, poses
   ni semilla, y no encontraba su última corrida. La UI restaura la definición
   congelada y consulta `GET /evaluation/cohorts/{id}/runs/latest`.
5. Los errores 422 de FastAPI perdían su detalle porque los arreglos se trataban
   como objetos genéricos. El cliente muestra ahora el mensaje accionable.
6. La interfaz exponía constantes internas. Bloqueos, avisos, abstenciones y
   fallos se presentan en lenguaje de producto.

## UX/UI y calidad

La auditoría Hallmark llevó a elevar contraste y peso tipográfico, eliminar
tarjetas anidadas en los contadores, usar números tabulares, añadir
`aria-pressed` a filtros y un estado vacío explícito. La reestructuración visual
amplia sigue diferida; la virtualización de cohortes extremas queda como P2 de
eficiencia, sin impacto sobre cálculo, persistencia o interpretación.

## Verificación automatizada

- backend completo: `937 passed, 3 skipped`;
- frontend completo: `548 passed` en 54 archivos;
- Batch enfocado tras la recuperación por cohorte: backend `42 passed`, frontend
  `15 passed`;
- TypeScript: `tsc --noEmit`, limpio;
- gate Vina/Meeko real: `PASS`.

Evaluación y Batch quedan verdes. El siguiente cierre vertical es Moldex.
